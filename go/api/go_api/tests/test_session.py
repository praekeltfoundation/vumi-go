"""Tests for go.api.go_api.session."""

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.api.go_api.session import SessionStore, CreateError
    from go.base.tests.helpers import GoDjangoTestCase


class TestSessionStore(GoDjangoTestCase):
    def mk_session_store(self, session_key=None):
        ss = SessionStore(session_key)
        return (ss, ss.session_manager)

    def test_init(self):
        ss, sm = self.mk_session_store()
        self.assertTrue(ss.session_key is None)
        ss, sm = self.mk_session_store(u"foo")
        self.assertEqual(ss.session_key, u"foo")

    def test_encode(self):
        ss, sm = self.mk_session_store()
        session = {"foo": 1}
        self.assertEqual(ss.encode(session), session)

    def test_decode(self):
        ss, sm = self.mk_session_store()
        session = {"foo": 1}
        self.assertEqual(ss.decode(session), session)

    def test_load_exists(self):
        ss, sm = self.mk_session_store(u"session-1")
        session = {"foo": 1}
        sm.save_session(u"session-1", session, 10)
        self.assertEqual(ss.load(), session)

    def test_load_new(self):
        ss, sm = self.mk_session_store()
        self.assertEqual(ss.load(), {})
        self.assertEqual(sm.get_session(ss.session_key), {})

    def test_exists(self):
        ss, sm = self.mk_session_store(u"session-1")
        self.assertEqual(ss.exists(u"session-1"), False)
        sm.save_session(u"session-1", {}, 10)
        self.assertEqual(ss.exists(u"session-1"), True)

    def test_create(self):
        ss, sm = self.mk_session_store()
        ss.create()
        self.assertFalse(ss.session_key is None)
        self.assertEqual(sm.get_session(ss.session_key), {})

    def test_save(self):
        ss, sm = self.mk_session_store()
        ss["foo"] = 1
        ss.save()
        self.assertEqual(sm.get_session(ss.session_key), {"foo": 1})
        ss["bar"] = 2
        ss.save()
        self.assertEqual(sm.get_session(ss.session_key),
                         {"foo": 1, "bar": 2})
        self.assertTrue(sm.session_ttl(ss.session_key) is not None)

    def test_save_must_create(self):
        ss, sm = self.mk_session_store()
        ss["foo"] = 1
        ss.save(must_create=True)
        self.assertEqual(sm.get_session(ss.session_key), {"foo": 1})

    def test_save_must_create_fails(self):
        ss, sm = self.mk_session_store(u"session-1")
        sm.save_session(u"session-1", {}, 10)
        self.assertRaises(CreateError, ss.save, must_create=True)

    def test_delete(self):
        ss, sm = self.mk_session_store(u"session-1")
        sm.save_session(u"session-1", {}, 10)
        ss.delete()
        self.assertFalse(sm.exists(u"session-1"))

    def test_delete_specific_session(self):
        ss, sm = self.mk_session_store()
        sm.save_session(u"session-1", {}, 10)
        ss.delete(u"session-1")
        self.assertFalse(sm.exists(u"session-1"))

    def test_delete_nothing(self):
        ss, sm = self.mk_session_store()
        ss.delete()
