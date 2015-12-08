# -*- coding: utf-8 -*-
# -*- test-case-name: go.api.go_api.tests.test_auth -*-

import urlparse

from zope.interface import implementer

import treq

from twisted.cred import portal, checkers, credentials, error
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import resource
from twisted.web.guard import HTTPAuthSessionWrapper, BasicCredentialFactory
from twisted.web.iweb import ICredentialFactory


@implementer(portal.IRealm)
class GoUserRealm(object):

    def __init__(self, resource_for_user):
        self._resource_for_user = resource_for_user

    def requestAvatar(self, user, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, self._resource_for_user(user),
                    lambda: None)
        raise NotImplementedError()


@implementer(checkers.ICredentialsChecker)
class GoUserSessionAccessChecker(object):
    """Checks that a username and password matches some constant (usually
    "session") and a Go session id.
    """

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


@implementer(ICredentialFactory)
class GoAuthBouncerCredentialFactory(BasicCredentialFactory):

    scheme = 'bearer'

    def decode(self, response, request):
        return GoAuthBouncerCredentials(request)


class IGoAuthBouncerCredentials(credentials.ICredentials):
    def get_request():
        """ Return the request to be authenticated. """


@implementer(IGoAuthBouncerCredentials)
class GoAuthBouncerCredentials(object):

    def __init__(self, request):
        self._request = request

    def get_request(self):
        return self._request


@implementer(checkers.ICredentialsChecker)
class GoAuthBouncerAccessChecker(object):
    """Checks that a username and password matches some constant (usually
    "session") and a Go session id.
    """

    credentialInterfaces = (IGoAuthBouncerCredentials,)

    def __init__(self, auth_bouncer_url):
        self._auth_bouncer_url = auth_bouncer_url

    @inlineCallbacks
    def _auth_request(self, request):
        auth = request.getHeader('Authorization')
        if not auth:
            returnValue(None)
        auth_headers = {'Authorization': auth}
        uri = urlparse.urljoin(self._auth_bouncer_url, request.path)
        resp = yield treq.get(uri, headers=auth_headers, persistent=False)
        if resp.code >= 400:
            returnValue(None)
        x_owner_id = resp.headers.getRawHeaders('X-Owner-Id')
        if x_owner_id is None or len(x_owner_id) != 1:
            returnValue(None)
        returnValue(x_owner_id[0])

    @inlineCallbacks
    def requestAvatarId(self, credentials):
        request = credentials.get_request()
        user_account_key = yield self._auth_request(request)
        if user_account_key:
            returnValue(user_account_key)
        raise error.UnauthorizedLogin()


class GoUserAuthSessionWrapper(HTTPAuthSessionWrapper):

    AUTHENTICATION_REALM = "Vumi Go API"

    def __init__(self, realm, vumi_api, auth_bouncer_url=None):
        checkers = [GoUserSessionAccessChecker(vumi_api.session_manager)]
        factories = [BasicCredentialFactory(self.AUTHENTICATION_REALM)]
        if auth_bouncer_url:
            checkers.append(GoAuthBouncerAccessChecker(auth_bouncer_url))
            factories.append(
                GoAuthBouncerCredentialFactory(self.AUTHENTICATION_REALM))

        p = portal.Portal(realm, checkers)
        super(GoUserAuthSessionWrapper, self).__init__(p, factories)
