
from twisted.internet.defer import inlineCallbacks

from vumi.config import ConfigError
from vumi.tests.helpers import VumiTestCase

from go.services.metrics.service_component import MetricsStoreServiceComponent
from go.services.tests.helpers import ServiceComponentHelper


class TestMetricsServiceComponent(VumiTestCase):
    is_sync = True

    @inlineCallbacks
    def setUp(self):
        self.service_helper = yield self.add_helper(
            ServiceComponentHelper(u'metrics', is_sync=self.is_sync))

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


class TestMetricsServiceComponentAsync(TestMetricsServiceComponent):
    is_sync = False
