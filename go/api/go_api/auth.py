# -*- coding: utf-8 -*-
# -*- test-case-name: go.api.go_api.tests.test_auth -*-

from zope.interface import implements

from twisted.cred import portal, checkers, credentials, error
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import resource
from twisted.web.guard import HTTPAuthSessionWrapper, BasicCredentialFactory


class GoUserRealm(object):
    implements(portal.IRealm)

    def __init__(self, resource):
        self.resource = resource

    def requestAvatar(self, user, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, self.resource, lambda: None)
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
        username = yield self.vumi_api.username_for_session(session_id)
        if username:
            returnValue(username)
        raise error.UnauthorizedLogin()


def protect_resource(self, resource, vumi_api):
    checkers = [
        GoUserSessionAccessChecker(vumi_api),
    ]
    realm = GoUserRealm(resource)
    p = portal.Portal(realm, checkers)

    factory = BasicCredentialFactory("Vumi Go Realm")
    protected_resource = HTTPAuthSessionWrapper(p, [factory])
    return protected_resource
