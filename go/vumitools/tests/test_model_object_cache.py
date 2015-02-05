from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.task import Clock

from vumi.tests.helpers import VumiTestCase

from go.vumitools.model_object_cache import ModelObjectCache
from go.vumitools.tests.helpers import VumiApiHelper


class FakeModelObject(object):
    """
    A stand-in for a model object fetched from Riak.
    """

    def __init__(self, key):
        self.key = key


class TestModelObjectCache(VumiTestCase):
    def setUp(self):
        self.clock = Clock()

    def make_object_getter(self, missing_keys=(), delay=0):
        """
        Build a function that returns a fake model object after a suitable
        delay for any key not in the missing keys list.
        """
        def object_getter(key):
            d = Deferred()
            obj = None if key in missing_keys else FakeModelObject(key)
            if delay > 0:
                self.clock.callLater(delay, d.callback, obj)
            else:
                d.callback(obj)
            return d

        return object_getter

    @inlineCallbacks
    def test_get_model_not_cached(self):
        """
        When fetching an uncached model, we cache it.
        """
        cache = ModelObjectCache(self.clock, 5)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

        getter = self.make_object_getter()
        model = yield cache.get_model(getter, "LisaFonssagrives")
        self.assertEqual(model.key, "LisaFonssagrives")
        self.assertEqual(cache._models, {"LisaFonssagrives": model})
        self.assertEqual(cache._evictors.keys(), ["LisaFonssagrives"])

        # Clean up remaining state.
        cache.cleanup()
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

    @inlineCallbacks
    def test_cache_eviction(self):
        """
        When the TTL is reached, the model is removed from the cache.
        """
        cache = ModelObjectCache(self.clock, 5)
        getter = self.make_object_getter()
        model = yield cache.get_model(getter, "LisaFonssagrives")
        self.assertEqual(model.key, "LisaFonssagrives")
        self.assertEqual(cache._models, {"LisaFonssagrives": model})
        self.assertEqual(cache._evictors.keys(), ["LisaFonssagrives"])

        self.clock.advance(4.9)
        self.assertNotEqual(cache._models, {})
        self.assertNotEqual(cache._evictors, {})

        self.clock.advance(0.5)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

    @inlineCallbacks
    def test_multiple_cache_eviction(self):
        """
        Each model has its own TTL.
        """
        cache = ModelObjectCache(self.clock, 5)
        getter = self.make_object_getter()
        model = yield cache.get_model(getter, "LisaFonssagrives")
        self.assertEqual(cache._models, {"LisaFonssagrives": model})
        self.assertEqual(cache._evictors.keys(), ["LisaFonssagrives"])

        self.clock.advance(3)
        model2 = yield cache.get_model(getter, "JinxFalkenburg")
        self.assertEqual(cache._models, {
            "LisaFonssagrives": model,
            "JinxFalkenburg": model2,
        })
        self.assertEqual(
            set(cache._evictors.keys()),
            set(["LisaFonssagrives", "JinxFalkenburg"]))

        self.clock.advance(3)
        self.assertEqual(cache._models, {
            "JinxFalkenburg": model2,
        })
        self.assertEqual(cache._evictors.keys(), ["JinxFalkenburg"])

        self.clock.advance(3)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

    @inlineCallbacks
    def test_get_model_no_caching(self):
        """
        When caching is disabled, we always fetch the model and never
        store it.
        """
        cache = ModelObjectCache(self.clock, 0)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

        getter = self.make_object_getter()
        model = yield cache.get_model(getter, "LisaFonssagrives")
        self.assertEqual(model.key, "LisaFonssagrives")
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

    @inlineCallbacks
    def test_schedule_duplicate_eviction(self):
        """
        If we schedule an eviction that already exists, we keep the old one
        instead.
        """
        cache = ModelObjectCache(self.clock, 5)
        getter = self.make_object_getter()
        yield cache.get_model(getter, "LisaFonssagrives")
        self.assertEqual(cache._evictors.keys(), ["LisaFonssagrives"])

        delayed_call = cache._evictors["LisaFonssagrives"]
        self.clock.advance(1)

        # Calling schedule_eviction() doesn't replace the existing one.
        cache.schedule_eviction("LisaFonssagrives")
        self.assertNotEqual(cache._models, {})
        self.assertEqual(cache._evictors["LisaFonssagrives"], delayed_call)

        # The existing eviction happens at the expected time.
        self.clock.advance(4)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

        # Advance to the time the new eviction would have been schduled to make
        # sure nothing breaks.
        self.clock.advance(1)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

    @inlineCallbacks
    def test_get_missing_model(self):
        """
        If a getter returns None instead of a model, the None is cached.
        """
        cache = ModelObjectCache(self.clock, 5)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

        getter = self.make_object_getter(missing_keys=["TinLizzy"])
        model = yield cache.get_model(getter, "TinLizzy")
        self.assertEqual(model, None)
        self.assertEqual(cache._models, {"TinLizzy": None})
        self.assertEqual(cache._evictors.keys(), ["TinLizzy"])

        # Clean up remaining state.
        cache.cleanup()
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

    def test_overlapping_gets(self):
        """
        If there are multiple pending gets for the same uncached key, the
        cached value will be replaced when each returns.
        """
        cache = ModelObjectCache(self.clock, 5)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

        getter = self.make_object_getter(delay=3)
        getter_missing = self.make_object_getter(
            missing_keys=["LisaFonssagrives"], delay=1)
        model1_d = cache.get_model(getter, "LisaFonssagrives")
        self.clock.advance(1)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors.keys(), [])

        model2_d = cache.get_model(getter_missing, "LisaFonssagrives")
        self.clock.advance(1)
        model2 = self.successResultOf(model2_d)
        self.assertNoResult(model1_d)
        self.assertEqual(model2, None)
        self.assertEqual(cache._models, {"LisaFonssagrives": None})
        self.assertEqual(cache._evictors.keys(), ["LisaFonssagrives"])

        self.clock.advance(1)
        model1 = self.successResultOf(model1_d)
        self.assertEqual(model1.key, "LisaFonssagrives")
        self.assertEqual(cache._models, {"LisaFonssagrives": model1})
        self.assertEqual(cache._evictors.keys(), ["LisaFonssagrives"])

        # Clean up remaining state.
        cache.cleanup()
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

    @inlineCallbacks
    def test_get_account_object(self):
        """
        The cache works correctly when fetching real model objects.
        """
        vumi_helper = yield self.add_helper(VumiApiHelper())
        user_helper = yield vumi_helper.make_user(u'testuser')
        account_key = user_helper.account_key

        cache = ModelObjectCache(self.clock, 5)
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})

        getter = vumi_helper.get_vumi_api().get_user_account
        model = yield cache.get_model(getter, account_key)
        self.assertEqual(model.key, account_key)
        self.assertEqual(cache._models, {account_key: model})
        self.assertEqual(cache._evictors.keys(), [account_key])

        # Clean up remaining state.
        cache.cleanup()
        self.assertEqual(cache._models, {})
        self.assertEqual(cache._evictors, {})
