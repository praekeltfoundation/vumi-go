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

    EXPECTED_USERNAME = "session_id"

    def __init__(self, session_manager):
        self.session_manager = session_manager

    @inlineCallbacks
    def requestAvatarId(self, credentials):
        if credentials.username != self.EXPECTED_USERNAME:
            raise error.UnauthorizedLogin()
        session_id = credentials.password
        session = yield self.session_manager.get_session(session_id)
        user_account_key = self.session_manager.get_user_account_key(session)
        if user_account_key:
            returnValue(user_account_key)
        raise error.UnauthorizedLogin()


class GoUserAuthSessionWrapper(HTTPAuthSessionWrapper):
    def __init__(self, realm, vumi_api):
        checkers = [
            GoUserSessionAccessChecker(vumi_api.session_manager),
        ]
        p = portal.Portal(realm, checkers)
        factory = BasicCredentialFactory("Vumi Go API")
        super(GoUserAuthSessionWrapper, self).__init__(p, [factory])
