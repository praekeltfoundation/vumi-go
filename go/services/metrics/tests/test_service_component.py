
from twisted.internet.defer import inlineCallbacks

from vumi.config import ConfigError
from vumi.tests.helpers import VumiTestCase

from go.services.metrics.service_component import (
    MetricsStoreServiceComponent, MissingMetricError)
from go.services.tests.helpers import ServiceComponentHelper


class TestMetricsServiceComponent(VumiTestCase):
    is_sync = True

    @inlineCallbacks
    def setUp(self):
        self.service_helper = yield self.add_helper(
            ServiceComponentHelper(u'metrics', is_sync=self.is_sync))

    def full_metric(self, metric_suffix, account_key="test-0-user"):
        return u'go.campaigns.%s.%s' % (account_key, metric_suffix)

    @inlineCallbacks
    def test_create_component(self):
        service = yield self.service_helper.create_service_component(
            name=u"myservice", config={u"metrics_prefix": u"foo"})
        service_api = yield self.service_helper.get_service_component_api(
            service.key)
        component = yield service_api.get_service_component_object(service)
        self.assertIsInstance(component, MetricsStoreServiceComponent)
        self.assertEqual(component.config.metrics_prefix, u"foo")

    @inlineCallbacks
    def test_create_component_invalid_config(self):
        service = yield self.service_helper.create_service_component(
            name=u"myservice")
        service_api = yield self.service_helper.get_service_component_api(
            service.key)
        try:
            yield service_api.get_service_component_object(service)
        except ConfigError:
            pass  # Expected failure
        except Exception as e:
            self.fail("Expected ConfigError, caught %s" % (e,))
        else:
            self.fail("Expected ConfigError, nothing raised.")

    @inlineCallbacks
    def test_fire_metric(self):
        service = yield self.service_helper.create_service_component(
            name=u"myservice", config={
                u"metrics_prefix": u"foo",
                u"metrics": [{u"name": u"bar"}],
            })
        service_api = yield self.service_helper.get_service_component_api(
            service.key)
        component = yield service_api.get_service_component_object(service)
        self.assertEqual(self.service_helper.get_published_metrics(), [])
        component.fire_metric("bar", 1)
        self.assertEqual(self.service_helper.get_published_metrics(), [
            (self.full_metric('stores.foo.bar'), 1),
        ])

    @inlineCallbacks
    def test_fire_metric_undefined(self):
        service = yield self.service_helper.create_service_component(
            name=u"myservice", config={u"metrics_prefix": u"foo"})
        service_api = yield self.service_helper.get_service_component_api(
            service.key)
        component = yield service_api.get_service_component_object(service)
        self.assertEqual(self.service_helper.get_published_metrics(), [])
        self.assertRaises(MissingMetricError, component.fire_metric, "bar", 1)
        self.assertEqual(self.service_helper.get_published_metrics(), [])

    @inlineCallbacks
    def test_fire_metric_multiple_aggregators(self):
        service = yield self.service_helper.create_service_component(
            name=u"myservice", config={
                u"metrics_prefix": u"foo",
                u"metrics": [
                    {u"name": u"bar", u"aggregators": ['min', 'max']},
                ],
            })
        service_api = yield self.service_helper.get_service_component_api(
            service.key)
        component = yield service_api.get_service_component_object(service)
        self.assertEqual(self.service_helper.get_published_metrics(), [])
        component.fire_metric("bar", 1)
        self.assertEqual(
            self.service_helper.get_published_metrics(aggregators=True), [
                (self.full_metric(u'stores.foo.bar'), ['max', 'min'], 1),
            ])


class TestMetricsServiceComponentAsync(TestMetricsServiceComponent):
    is_sync = False
