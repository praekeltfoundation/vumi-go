# -*- coding: utf-8 -*-

"""Tests for go.vumitools.router.models."""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.tests.utils import model_eq
from go.vumitools.router.models import RouterStore
from go.vumitools.tests.helpers import VumiApiHelper


class TestRouter(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        user_account = yield self.user_helper.get_user_account()
        self.router_store = RouterStore.from_user_account(user_account)

    def assert_status(self, router, expected_status_name, archived=False):
        for status_name in ['starting', 'running', 'stopping', 'stopped']:
            status_method = getattr(router, status_name)
            if status_name == expected_status_name:
                self.assertTrue(status_method(), 'Expected %s() to be True.')
            else:
                self.assertFalse(status_method(), 'Expected %s() to be False.')

        if archived:
            self.assertTrue(router.archived(), 'Expected archived.')
            self.assertFalse(router.active(), 'Expected not active.')
        else:
            self.assertTrue(router.active(), 'Expected active.')
            self.assertFalse(router.archived(), 'Expected not archived.')

    @inlineCallbacks
    def test_status_helpers(self):
        router = yield self.router_store.new_router(
            u'keyword_router', u'name', u'desc', {}, u'batch1')
        # A new router is "stopped" and "active".
        self.assert_status(router, 'stopped')
        router.set_status_starting()
        self.assert_status(router, 'starting')
        router.set_status_started()
        self.assert_status(router, 'running')
        router.set_status_stopping()
        self.assert_status(router, 'stopping')
        router.set_status_stopped()
        self.assert_status(router, 'stopped')
        router.set_status_finished()
        self.assert_status(router, 'stopped', archived=True)


class TestRouterStore(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        user_account = yield self.user_helper.get_user_account()
        self.router_store = RouterStore.from_user_account(user_account)

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
            u'keyword_router', u'name', u'desc', {u'foo': u'bar'}, u'batch1')
        self.assertEqual(u'keyword_router', router.router_type)
        self.assertEqual(u'name', router.name)
        self.assertEqual(u'desc', router.description)
        self.assertEqual({u'foo': u'bar'}, router.config)
        self.assertEqual(u'active', router.archive_status)
        self.assertEqual(u'stopped', router.status)
        self.assertEqual(u'batch1', router.batch.key)

        dbrouter = yield self.router_store.get_router_by_key(router.key)
        self.assert_models_equal(router, dbrouter)

    @inlineCallbacks
    def test_new_router_unicode(self):
        routers = yield self.router_store.list_routers()
        self.assertEqual([], routers)

        router = yield self.router_store.new_router(
            u'keyword_router', u'Zoë destroyer of Ascii', u'Return of Zoë!',
            {u'foo': u'Zoë again.'}, u'batch1')
        self.assertEqual(u'keyword_router', router.router_type)
        self.assertEqual(u'Zoë destroyer of Ascii', router.name)
        self.assertEqual(u'Return of Zoë!', router.description)
        self.assertEqual({u'foo': u'Zoë again.'}, router.config)
        self.assertEqual(u'active', router.archive_status)
        self.assertEqual(u'stopped', router.status)
        self.assertEqual(u'batch1', router.batch.key)

        dbrouter = yield self.router_store.get_router_by_key(router.key)
        self.assert_models_equal(router, dbrouter)


class TestRouterStoreSync(TestRouterStore):
    sync_persistence = True
