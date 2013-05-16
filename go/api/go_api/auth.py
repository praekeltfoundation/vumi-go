# -*- coding: utf-8 -*-
# -*- test-case-name: go.api.go_api.tests.test_auth -*-

from zope.interface import implements

from twisted.cred import portal, checkers, credentials, error
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import resource
from twisted.web.guard import HTTPAuthSessionWrapper, BasicCredentialFactory


class GoUserRealm(object):
    implements(portal.IRealm)

    def __init__(self, resource_for_user):
        self._resource_for_user = resource_for_user

    def resource_for_user(self, user):
        raise NotImplementedError()

    def requestAvatar(self, user, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, self._resource_for_user(user),
                    lambda: None)
        raise NotImplementedError()


class GoUserSessionAccessChecker(object):
    """Checks that a username and password matches some constant (usually
    "session") and a Go session id.
    """

    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,)

    EXPECTED_USERNAME = "session"

    def __init__(self, vumi_api):
        self.vumi_api = vumi_api

    @inlineCallbacks
    def requestAvatarId(self, credentials):
        if credentials.username != self.EXPECTED_USERNAME:
            raise error.UnauthorizedLogin()
        session_id = credentials.password
        user = yield self.vumi_api.username_for_session(session_id)
        if user:
            returnValue(user)
        raise error.UnauthorizedLogin()


class GoUserAuthSessionWrapper(HTTPAuthSessionWrapper):
    def __init__(self, realm, vumi_api):
        checkers = [
            GoUserSessionAccessChecker(vumi_api),
        ]
        p = portal.Portal(realm, checkers)
        factory = BasicCredentialFactory("Vumi Go API")
        super(GoUserAuthSessionWrapper, self).__init__(p, [factory])
