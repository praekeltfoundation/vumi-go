import json

from vumi.config import ConfigError
from vumi.tests.helpers import VumiTestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from go.services.kvstore.redis.service_component import (
    RedisKVStoreServiceComponent)
from go.services.tests.helpers import ServiceComponentHelper


class TestMetricsServiceComponent(VumiTestCase):
    is_sync = True

    @inlineCallbacks
    def setUp(self):
        self.service_helper = yield self.add_helper(
            ServiceComponentHelper(u'kvstore.redis', is_sync=self.is_sync))

    @inlineCallbacks
    def build_component(self, config_override=None, name=u"myservice"):
        config = {
            u"key_prefix": u"foo.prefix",
            u"keys_per_user": 5,
        }
        if config_override is not None:
            config.update(config_override)
        service = yield self.service_helper.create_service_component(
            name=name, config=config)
        service_api = yield self.service_helper.get_service_component_api(
            service.key)
        component = yield service_api.get_service_component_object(service)
        returnValue(component)

    @inlineCallbacks
    def assert_key_count(self, component, expected):
        key_count = yield component.redis.get(component._count_key())
        self.assertEqual(int(key_count or 0), expected)

    @inlineCallbacks
    def increment_key_count(self, component, value, expected=None):
        if expected is None:
            expected = value
        key_count = yield component.redis.incr(component._count_key(), value)
        self.assertEqual(key_count, expected)

    @inlineCallbacks
    def test_create_component(self):
        service = yield self.service_helper.create_service_component(
            name=u"myservice", config={
                u"key_prefix": u"foo.prefix",
                u"keys_per_user": 10,
            })
        service_api = yield self.service_helper.get_service_component_api(
            service.key)
        component = yield service_api.get_service_component_object(service)
        self.assertIsInstance(component, RedisKVStoreServiceComponent)
        self.assertEqual(component.redis._key_prefix, "foo.prefix")
        self.assertEqual(component.keys_per_user_hard, 10)
        self.assertEqual(component.keys_per_user_soft, 8)

    @inlineCallbacks
    def test_create_component_default_config(self):
        service = yield self.service_helper.create_service_component(
            name=u"myservice", config={})
        service_api = yield self.service_helper.get_service_component_api(
            service.key)
        component = yield service_api.get_service_component_object(service)
        # These values come from go.config.
        self.assertEqual(component.config.key_prefix, 'vumigo.jsbox.kv')
        self.assertEqual(component.config.keys_per_user, 10000)

    @inlineCallbacks
    def test_check_keys_below_limits(self):
        component = yield self.build_component({})
        result = yield component.check_keys("foo")
        self.assertEqual(result, True)

    @inlineCallbacks
    def test_check_keys_soft_limit(self):
        component = yield self.build_component({})
        yield self.increment_key_count(component, 4)
        # TODO: Assert soft limit log messages
        result = yield component.check_keys("foo")
        self.assertEqual(result, True)

    @inlineCallbacks
    def test_check_keys_hard_limit(self):
        component = yield self.build_component({})
        yield self.increment_key_count(component, 6)
        # TODO: Assert hard limit log messages
        result = yield component.check_keys("foo")
        self.assertEqual(result, False)

    @inlineCallbacks
    def test_check_keys_existing_key(self):
        component = yield self.build_component({})
        yield component.redis.set("foo", "bar")
        yield self.increment_key_count(component, 6)
        # TODO: Assert no log messages
        result = yield component.check_keys("foo")
        self.assertEqual(result, True)

    @inlineCallbacks
    def test_set_value(self):
        component = yield self.build_component({})
        yield self.assert_key_count(component, 0)

        yield component.set_value("foo", "bar")
        stored = yield component.redis.get(component._sandboxed_key("foo"))
        self.assertEqual(json.loads(stored), "bar")
        yield self.assert_key_count(component, 1)

        yield component.set_value("foo", "baz")
        stored = yield component.redis.get(component._sandboxed_key("foo"))
        self.assertEqual(json.loads(stored), "baz")
        yield self.assert_key_count(component, 1)

    @inlineCallbacks
    def test_get_value(self):
        component = yield self.build_component({})
        yield component.redis.set(
            component._sandboxed_key("foo"), json.dumps("bar"))
        value = yield component.get_value("foo")
        self.assertEqual(value, "bar")

    @inlineCallbacks
    def test_get_value_default(self):
        component = yield self.build_component({})
        value = yield component.get_value("foo", "default")
        self.assertEqual(value, "default")

    @inlineCallbacks
    def test_delete_value(self):
        component = yield self.build_component({})
        yield component.redis.set(component._sandboxed_key("foo"), "bar")
        yield self.increment_key_count(component, 1)
        result = yield component.delete_value("foo")
        self.assertEqual(result, True)
        yield self.assert_key_count(component, 0)

    @inlineCallbacks
    def test_delete_value_no_key(self):
        component = yield self.build_component({})
        yield self.assert_key_count(component, 0)
        result = yield component.delete_value("foo")
        yield self.assert_key_count(component, 0)
        self.assertEqual(result, False)


class TestMetricsServiceComponentAsync(TestMetricsServiceComponent):
    is_sync = False
