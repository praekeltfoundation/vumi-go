"""Test for go.api.go_api.auth."""

import base64

from twisted.cred import error
from twisted.cred.credentials import UsernamePassword
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase
from twisted.web import resource
from twisted.web.test.test_web import DummyRequest

from go.api.go_api.auth import (
    GoUserRealm, GoUserSessionAccessChecker, GoUserAuthSessionWrapper)
from go.api.go_api.session_manager import SessionManager
from go.vumitools.api import VumiApi
from go.vumitools.tests.utils import GoPersistenceMixin

import mock


class GoUserRealmTestCase(TestCase):
    def test_request_avatar(self):
        expected_resource = object()
        getter = mock.Mock(return_value=expected_resource)
        mind = object()
        realm = GoUserRealm(getter)
        interface, web_resource, cleanup = realm.requestAvatar(
            u"user", mind, resource.IResource)
        self.assertTrue(getter.called_once_with(u"user"))
        self.assertTrue(interface is resource.IResource)
        self.assertTrue(web_resource is expected_resource)
        cleanup()  # run clean-up function to check it doesn't error

    def test_request_avatar_without_iresource_interface(self):
        def getter(user):
            self.fail("Unexpected call to resource retrieval function")
        mind = object()

        realm = GoUserRealm(getter)
        self.assertRaises(NotImplementedError,
                          realm.requestAvatar, u"user", mind)


class GoUserSessionAccessCheckerTestCase(TestCase, GoPersistenceMixin):
    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        self.redis = yield self.get_redis_manager()
        self.sm = SessionManager(self.redis)

    @inlineCallbacks
    def tearDown(self):
        yield self._persist_tearDown()

    @inlineCallbacks
    def test_request_avatar_id(self):
        checker = GoUserSessionAccessChecker(self.sm)
        session = {}
        self.sm.set_user_account_key(session, u"user-1")
        yield self.sm.save_session(u"session-1", session, 10)
        creds = UsernamePassword(u"session_id", u"session-1")
        user = yield checker.requestAvatarId(creds)
        self.assertEqual(user, u"user-1")

    @inlineCallbacks
    def test_request_avatar_id_bad_password(self):
        checker = GoUserSessionAccessChecker(self.sm)
        creds = UsernamePassword(u"session_id", u"session-unknown")
        errored = False
        try:
            yield checker.requestAvatarId(creds)
        except error.UnauthorizedLogin:
            errored = True
        self.assertTrue(errored)

    @inlineCallbacks
    def test_request_avatar_id_bad_username(self):
        checker = GoUserSessionAccessChecker(self.sm)
        session = {}
        self.sm.set_user_account_key(session, u"user-1")
        yield  self.sm.save_session(u"session-1", session, 10)
        creds = UsernamePassword(u"session_id_BAD", u"session-1")
        try:
            yield checker.requestAvatarId(creds)
        except error.UnauthorizedLogin:
            errored = True
        self.assertTrue(errored)


class GoUserAuthSessionWrapperTestCase(TestCase, GoPersistenceMixin):

    use_riak = True

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        self.config = self.mk_config({})
        self.vumi_api = yield VumiApi.from_config_async(self.config)

    @inlineCallbacks
    def tearDown(self):
        yield self._persist_tearDown()

    def mk_request(self, user=None, password=None):
        request = DummyRequest([''])
        if user is not None:
            request.headers["authorization"] = (
                "Basic %s" % base64.b64encode("%s:%s" % (user, password))
            )
        return request

    def mk_wrapper(self, text):
        class TestResource(resource.Resource):
            isLeaf = True

            def __init__(self, user):
                self.user = user

            def render(self, request):
                request.setResponseCode(200)
                return "%s: %s" % (text, self.user.encode("utf-8"))

        realm = GoUserRealm(lambda user: TestResource(user))
        wrapper = GoUserAuthSessionWrapper(realm, self.vumi_api)
        return wrapper

    @inlineCallbacks
    def check_request(self, wrapper, request, expected_code, expected_body):
        finished = request.notifyFinish()
        wrapper.render(request)
        yield finished
        self.assertTrue(request.finished)
        self.assertEqual(request.responseCode, expected_code)
        self.assertEqual("".join(request.written), expected_body)

    @inlineCallbacks
    def test_auth_success(self):
        session = {}
        self.vumi_api.session_manager.set_user_account_key(session, u"user-1")
        yield self.vumi_api.session_manager.save_session(
            u"session-1", session, 10)
        wrapper = self.mk_wrapper("FOO")
        request = self.mk_request(u"session_id", u"session-1")
        yield self.check_request(wrapper, request, 200, "FOO: user-1")

    @inlineCallbacks
    def test_auth_failure(self):
        wrapper = self.mk_wrapper("FOO")
        request = self.mk_request()
        yield self.check_request(wrapper, request, 401, "Unauthorized")
