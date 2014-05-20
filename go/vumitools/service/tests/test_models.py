# -*- coding: utf-8 -*-

"""Tests for go.vumitools.service.models."""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.tests.utils import model_eq
from go.vumitools.service.models import ServiceComponentStore
from go.vumitools.tests.helpers import VumiApiHelper


class TestService(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        account = yield self.user_helper.get_user_account()
        self.service_store = ServiceComponentStore.from_user_account(account)

    def assert_status(self, service, expected_status_name, archived=False):
        for status_name in ['starting', 'running', 'stopping', 'stopped']:
            status_method = getattr(service, status_name)
            if status_name == expected_status_name:
                self.assertTrue(status_method(), 'Expected %s() to be True.')
            else:
                self.assertFalse(status_method(), 'Expected %s() to be False.')

        if archived:
            self.assertTrue(service.archived(), 'Expected archived.')
            self.assertFalse(service.active(), 'Expected not active.')
        else:
            self.assertTrue(service.active(), 'Expected active.')
            self.assertFalse(service.archived(), 'Expected not archived.')

    @inlineCallbacks
    def test_status_helpers(self):
        service = yield self.service_store.new_service_component(
            u'dummy_service', u'name', u'desc', {})
        # A new service is "stopped" and "active".
        self.assert_status(service, 'stopped')
        service.set_status_starting()
        self.assert_status(service, 'starting')
        service.set_status_started()
        self.assert_status(service, 'running')
        service.set_status_stopping()
        self.assert_status(service, 'stopping')
        service.set_status_stopped()
        self.assert_status(service, 'stopped')
        service.set_status_finished()
        self.assert_status(service, 'stopped', archived=True)


class TestServiceStore(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        account = yield self.user_helper.get_user_account()
        self.service_store = ServiceComponentStore.from_user_account(account)

    def assert_models_equal(self, m1, m2):
        self.assertTrue(model_eq(m1, m2),
                        "Models not equal:\na: %r\nb: %r" % (m1, m2))

    def assert_models_not_equal(self, m1, m2):
        self.assertFalse(model_eq(m1, m2),
                         "Models unexpectedly equal:\na: %r\nb: %r" % (m1, m2))

    @inlineCallbacks
    def test_new_service_component(self):
        services = yield self.service_store.list_service_components()
        self.assertEqual([], services)

        service = yield self.service_store.new_service_component(
            u'dummy_service', u'name', u'desc', {u'foo': u'bar'})
        self.assertEqual(u'dummy_service', service.service_component_type)
        self.assertEqual(u'name', service.name)
        self.assertEqual(u'desc', service.description)
        self.assertEqual({u'foo': u'bar'}, service.config)
        self.assertEqual(u'active', service.archive_status)
        self.assertEqual(u'stopped', service.status)

        dbservice = yield self.service_store.get_service_component_by_key(
            service.key)
        self.assert_models_equal(service, dbservice)

    @inlineCallbacks
    def test_new_service_component_unicode(self):
        services = yield self.service_store.list_service_components()
        self.assertEqual([], services)

        service = yield self.service_store.new_service_component(
            u'dummy_service', u'Zoë destroyer of Ascii', u'Return of Zoë!',
            {u'foo': u'Zoë again.'})
        self.assertEqual(u'dummy_service', service.service_component_type)
        self.assertEqual(u'Zoë destroyer of Ascii', service.name)
        self.assertEqual(u'Return of Zoë!', service.description)
        self.assertEqual({u'foo': u'Zoë again.'}, service.config)
        self.assertEqual(u'active', service.archive_status)
        self.assertEqual(u'stopped', service.status)

        dbservice = yield self.service_store.get_service_component_by_key(
            service.key)
        self.assert_models_equal(service, dbservice)

    @inlineCallbacks
    def test_list_service_components_for_type(self):
        store = self.service_store
        foo_service = yield store.new_service_component(
            u'foo_service', u'name', u'desc', {u'foo': u'bar'})
        bar_service = yield store.new_service_component(
            u'bar_service', u'name', u'desc', {u'foo': u'bar'})
        foo_keys = yield store.list_service_components_for_type(u'foo_service')
        bar_keys = yield store.list_service_components_for_type(u'bar_service')
        self.assertEqual([foo_service.key], foo_keys)
        self.assertEqual([bar_service.key], bar_keys)

    @inlineCallbacks
    def test_list_service_components_for_interface(self):
        # TODO: Test multiple service types with the same interface
        # TODO: Test a service type with multiple interfaces
        store = self.service_store
        yield store.new_service_component(
            u'foo_service', u'name', u'desc', {u'foo': u'bar'})
        metrics_service = yield store.new_service_component(
            u'metrics', u'name', u'desc', {u'foo': u'bar'})
        metrics_keys = yield store.list_service_components_for_interface(
            u'metrics')
        self.assertEqual([metrics_service.key], metrics_keys)


class TestServiceStoreSync(TestServiceStore):
    sync_persistence = True
