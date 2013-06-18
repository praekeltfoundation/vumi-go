# -*- coding: utf-8 -*-

"""Tests for go.vumitools.router.models."""

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from go.vumitools.tests.utils import model_eq, GoPersistenceMixin
from go.vumitools.account import AccountStore
from go.vumitools.router.models import RouterStore


class TestRouterStore(GoPersistenceMixin, TestCase):
    use_riak = True
    timeout = 5

    @inlineCallbacks
    def setUp(self):
        yield self._persist_setUp()
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        self.account = yield self.mk_user(self, u'user')
        self.router_store = RouterStore.from_user_account(self.account)

    def tearDown(self):
        return self._persist_tearDown()

    def assert_models_equal(self, m1, m2):
        self.assertTrue(model_eq(m1, m2),
                        "Models not equal:\na: %r\nb: %r" % (m1, m2))

    def assert_models_not_equal(self, m1, m2):
        self.assertFalse(model_eq(m1, m2),
                         "Models unexpectedly equal:\na: %r\nb: %r" % (m1, m2))

    @inlineCallbacks
    def test_new_router(self):
        routers = yield self.router_store.list_routers()
        self.assertEqual([], routers)

        router = yield self.router_store.new_router(
            u'keyword_router', u'name', u'desc', {u'foo': u'bar'})
        self.assertEqual(u'keyword_router', router.router_type)
        self.assertEqual(u'name', router.name)
        self.assertEqual(u'desc', router.description)
        self.assertEqual({u'foo': u'bar'}, router.config)
        self.assertEqual(u'active', router.archive_status)
        self.assertEqual(u'stopped', router.status)

        dbrouter = yield self.router_store.get_router_by_key(router.key)
        self.assert_models_equal(router, dbrouter)

    @inlineCallbacks
    def test_new_router_unicode(self):
        routers = yield self.router_store.list_routers()
        self.assertEqual([], routers)

        router = yield self.router_store.new_router(
            u'keyword_router', u'Zoë destroyer of Ascii', u'Return of Zoë!',
            {u'foo': u'Zoë again.'})
        self.assertEqual(u'keyword_router', router.router_type)
        self.assertEqual(u'Zoë destroyer of Ascii', router.name)
        self.assertEqual(u'Return of Zoë!', router.description)
        self.assertEqual({u'foo': u'Zoë again.'}, router.config)
        self.assertEqual(u'active', router.archive_status)
        self.assertEqual(u'stopped', router.status)

        dbrouter = yield self.router_store.get_router_by_key(router.key)
        self.assert_models_equal(router, dbrouter)


class TestRouterStoreSync(TestRouterStore):
    sync_persistence = True
