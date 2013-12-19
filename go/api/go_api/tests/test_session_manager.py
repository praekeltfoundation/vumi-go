"""Tests for go.api.go_api.session_manager."""

import json

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.api.go_api.session_manager import SessionManager, GO_USER_ACCOUNT_KEY


class TestSessionManager(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = self.add_helper(PersistenceHelper())
        self.redis = yield self.persistence_helper.get_redis_manager()
        self.sm = SessionManager(self.redis)

    @inlineCallbacks
    def mk_session(self, session_id, session):
        key = "sessions.%s" % (session_id,)
        session_json = json.dumps(session)
        yield self.redis.set(key, session_json)

    def test_get_user_account_key(self):
        session = {
            GO_USER_ACCOUNT_KEY: u"user-1",
        }
        self.assertEqual(
            SessionManager.get_user_account_key(session),
            u"user-1")

    def test_get_user_account_key_missing(self):
        self.assertEqual(
            SessionManager.get_user_account_key({}),
            None)

    def test_get_user_account_key_for_none_session(self):
        self.assertEqual(
            SessionManager.get_user_account_key(None),
            None)

    def test_set_user_account_key(self):
        session = {}
        SessionManager.set_user_account_key(session, u"user-1")
        self.assertEqual(session, {
            GO_USER_ACCOUNT_KEY: u"user-1",
        })

    @inlineCallbacks
    def test_exists(self):
        self.assertEqual((yield self.sm.exists("unknown-session")), False)
        yield self.mk_session("session-1", {})
        self.assertEqual((yield self.sm.exists("session-1")), True)

    @inlineCallbacks
    def test_session_ttl(self):
        yield self.sm.save_session(u"session-1", {}, 10)
        self.assertTrue((yield self.sm.session_ttl(u"session-1")) <= 10)
        self.assertEqual((yield self.sm.session_ttl(u"session-unknown")), None)

    @inlineCallbacks
    def test_get_session(self):
        session = {
            "foo": {"thing": 1},
            "bar": "baz",
        }
        yield self.mk_session("session-1", session)
        self.assertEqual(
            (yield self.sm.get_session("session-1")),
            session)

    @inlineCallbacks
    def test_get_session_missing(self):
        self.assertEqual(
            (yield self.sm.get_session("session-1")),
            None)

    @inlineCallbacks
    def test_create_session_success(self):
        session = {"test": 1}
        created = (yield self.sm.create_session(
            u"session-1", session, 10))
        self.assertEqual(created, True)
        self.assertEqual(
            (yield self.redis.get("sessions.session-1")),
            json.dumps(session))

    @inlineCallbacks
    def test_create_session_fails(self):
        session = {"test": 1}
        yield self.mk_session(u"session-1", session)
        created = (yield self.sm.create_session(
            u"session-1", {"test": 2}, 10))
        self.assertEqual(created, False)
        # test session hasn't changed
        self.assertEqual(
            (yield self.redis.get("sessions.session-1")),
            json.dumps(session))

    @inlineCallbacks
    def test_save_session_new(self):
        session = {"test": 1}
        yield self.sm.save_session(
            u"session-1", session, 10)
        self.assertEqual(
            (yield self.redis.get("sessions.session-1")),
            json.dumps(session))

    @inlineCallbacks
    def test_save_session_existing(self):
        session = {"test": 1}
        yield self.mk_session(u"session-1", session)
        session = {"test": 2}
        yield self.sm.save_session(
            u"session-1", session, 10)
        self.assertEqual(
            (yield self.redis.get("sessions.session-1")),
            json.dumps(session))

    @inlineCallbacks
    def test_delete_session(self):
        yield self.mk_session(u"session-1", {})
        deleted = yield self.sm.delete_session(u"session-1")
        self.assertEqual(deleted, True)

    @inlineCallbacks
    def test_delete_session_missing(self):
        deleted = yield self.sm.delete_session(u"session-1")
        self.assertEqual(deleted, False)
