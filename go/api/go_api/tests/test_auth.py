"""Test for go.api.go_api.auth."""

from twisted.cred import error
from twisted.cred.credentials import UsernamePassword
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase
from twisted.web import resource

from go.api.go_api.auth import (
    GoUserRealm, GoUserSessionAccessChecker, GoUserAuthSessionWrapper)
from go.api.go_api.session_manager import SessionManager
from go.vumitools.tests.utils import GoPersistenceMixin


class GoUserRealmTestCase(TestCase):

    def mk_resource_and_getter(self):
        web_resource = object()
        calls = []

        def getter(user):
            calls.append(user)
            return web_resource

        return web_resource, calls, getter

    def test_request_avatar(self):
        expected_resource, calls, getter = self.mk_resource_and_getter()
        mind = object()
        realm = GoUserRealm(getter)
        interface, web_resource, cleanup = realm.requestAvatar(
            u"user", mind, resource.IResource)
        self.assertEqual(calls, [u"user"])
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


class GoUserAuthSessionWrapperTestCase(TestCase):
    def test_creation(self):
        self.fail("Still to implement.")
