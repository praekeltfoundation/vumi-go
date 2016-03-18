"""Tests for go.vumitools.middleware"""
import time

from twisted.internet.defer import inlineCallbacks, returnValue

from zope.interface import implements

from vumi.transports.failures import FailureMessage
from vumi.message import TransportUserMessage
from vumi.middleware.tagger import TaggingMiddleware
from vumi.tests.helpers import VumiTestCase, generate_proxies, IHelper
from vumi.worker import BaseWorker

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin
from go.vumitools.middleware import (
    NormalizeMsisdnMiddleware, OptOutMiddleware, MetricsMiddleware,
    ConversationStoringMiddleware, RouterStoringMiddleware,
    ConversationMetricsMiddleware)
from go.vumitools.tests.helpers import VumiApiHelper, GoMessageHelper


class ToyWorkerConfig(BaseWorker.CONFIG_CLASS, GoWorkerConfigMixin):
    pass


class ToyWorker(BaseWorker, GoWorkerMixin):
    CONFIG_CLASS = ToyWorkerConfig

    def setup_worker(self):
        return self._go_setup_worker()

    def teardown_worker(self):
        return self._go_teardown_worker()

    def setup_connectors(self):
        pass


class MiddlewareHelper(object):
    implements(IHelper)

    def __init__(self, middleware_class):
        self._vumi_helper = VumiApiHelper()
        self._msg_helper = GoMessageHelper()
        self.middleware_class = middleware_class
        self._middlewares = []

        generate_proxies(self, self._vumi_helper)
        generate_proxies(self, self._msg_helper)

    def setup(self):
        return self._vumi_helper.setup(setup_vumi_api=False)

    @inlineCallbacks
    def cleanup(self):
        for mw in self._middlewares:
            yield mw.teardown_middleware()
        yield self._vumi_helper.cleanup()

    @inlineCallbacks
    def create_middleware(self, config=None, middleware_class=None,
                          name='dummy_middleware'):
        worker_helper = self._vumi_helper.get_worker_helper()
        dummy_worker = yield worker_helper.get_worker(
            ToyWorker, self.mk_config({}))
        config = self.mk_config(config or {})
        if middleware_class is None:
            middleware_class = self.middleware_class
        mw = middleware_class(name, config, dummy_worker)
        self._middlewares.append(mw)
        yield mw.setup_middleware()
        returnValue(mw)


class TestNormalizeMisdnMiddleware(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.mw_helper = self.add_helper(
            MiddlewareHelper(NormalizeMsisdnMiddleware))
        self.mw = yield self.mw_helper.create_middleware({
            'country_code': '256',
        })

    def test_inbound_normalization(self):
        msg = self.mw_helper.make_inbound(
            "foo", to_addr='8007', from_addr='256123456789')
        msg = self.mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['from_addr'], '+256123456789')

    def test_inbound_normalization_of_null_from_addr(self):
        msg = self.mw_helper.make_inbound(
            "foo", to_addr='8007', from_addr=None)
        msg = self.mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['from_addr'], None)

    @inlineCallbacks
    def test_inbound_normalization_ignores_strip_plus(self):
        mw = yield self.mw_helper.create_middleware({
            'country_code': '256',
            'strip_plus': True,
        })
        msg = self.mw_helper.make_inbound(
            "foo", to_addr='8007', from_addr='+256123456789')
        msg = mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['from_addr'], '+256123456789')

    def test_outbound_normalization(self):
        msg = self.mw_helper.make_outbound(
            "foo", to_addr='0123456789', from_addr='8007')
        msg = self.mw.handle_outbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['to_addr'], '+256123456789')

    def test_outbound_normalization_of_null_to_addr(self):
        msg = self.mw_helper.make_outbound(
            "foo", to_addr=None, from_addr='8007')
        msg = self.mw.handle_outbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['to_addr'], None)

    @inlineCallbacks
    def test_outbound_normalization_applies_strip_plus(self):
        mw = yield self.mw_helper.create_middleware({
            'country_code': '256',
            'strip_plus': True,
        })
        msg = self.mw_helper.make_outbound(
            "foo", to_addr='0123456789', from_addr='8007')
        msg = mw.handle_outbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['to_addr'], '256123456789')


class TestOptOutMiddleware(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.mw_helper = self.add_helper(MiddlewareHelper(OptOutMiddleware))
        yield self.mw_helper.setup_vumi_api()
        self.config = {
            'optout_keywords': ['STOP', 'HALT', 'QUIT']
        }

    @inlineCallbacks
    def get_middleware(self, extra_config={}, extra_tagpool_metadata={}):
        config = self.config.copy()
        config.update(extra_config)
        mw = yield self.mw_helper.create_middleware(config)
        tagpool_metadata = {
            "transport_type": "other",
            "msg_options": {"transport_name": "other_transport"},
        }
        tagpool_metadata.update(extra_tagpool_metadata)
        yield self.mw_helper.setup_tagpool(
            "pool", ["tag1"], metadata=tagpool_metadata)
        returnValue(mw)

    @inlineCallbacks
    def send_keyword(self, mw, word, expected_response):
        msg = self.mw_helper.make_inbound(
            word, to_addr='to@domain.org', from_addr='from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, ("pool", "tag1"))
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        expected_response = dict(expected_response,
                                 tag={'tag': ['pool', 'tag1']})
        # MessageMetadataHelper can add 'go' metadata and we want to ignore it.
        if 'go' in msg['helper_metadata']:
            expected_response['go'] = msg['helper_metadata']['go']
        self.assertEqual(msg['helper_metadata'], expected_response)

    @inlineCallbacks
    def test_optout_flag(self):
        mw = yield self.get_middleware()
        for keyword in self.config['optout_keywords']:
            yield self.send_keyword(mw, keyword, {
                'optout': {
                    'optout': True,
                    'optout_keyword': keyword.lower(),
                }
            })

    @inlineCallbacks
    def test_non_optout_keywords(self):
        mw = yield self.get_middleware()
        for keyword in ['THESE', 'DO', 'NOT', 'OPT', 'OUT']:
            yield self.send_keyword(mw, keyword, {
                'optout': {'optout': False},
            })

    @inlineCallbacks
    def test_disabled_by_tagpool(self):
        mw = yield self.get_middleware(extra_tagpool_metadata={
            "disable_global_opt_out": True,
        })
        yield self.send_keyword(mw, 'STOP', {
            'optout': {'optout': False},
        })

    @inlineCallbacks
    def test_case_sensitivity(self):
        mw = yield self.get_middleware({'case_sensitive': True})

        yield self.send_keyword(mw, 'STOP', {
            'optout': {
                'optout': True,
                'optout_keyword': 'STOP',
            }
        })

        yield self.send_keyword(mw, 'stop', {
            'optout': {
                'optout': False,
            }
        })


class TestMetricsMiddleware(VumiTestCase):

    def setUp(self):
        self.mw_helper = self.add_helper(MiddlewareHelper(MetricsMiddleware))

    def get_middleware(self, config):
        default_config = {
            'manager_name': 'metrics_manager',
            'count_suffix': 'counter',
            'response_time_suffix': 'timer',
        }
        default_config.update(config or {})
        return self.mw_helper.create_middleware(default_config)

    def assert_metrics(self, mw, metrics):
        for metric_name, expected in metrics.items():
            metric = mw.metric_manager[metric_name]
            metric_values = [m[1] for m in metric.poll()]
            if not isinstance(expected, dict):
                expected = {'values': expected}
            expected_values = expected.get('values')
            if callable(expected_values):
                self.assertTrue(all(
                    expected_values(v) for v in metric_values))
            else:
                self.assertEqual(metric_values, expected_values)
            expected_aggs = expected.get('aggs', ['sum'])
            self.assertEqual(set(metric.aggs), set(expected_aggs))

    def assert_metrics_absent(self, mw, metrics):
        for metric_name in metrics:
            self.assertFalse(metric_name in mw.metric_manager)

    @inlineCallbacks
    def assert_redis_timestamp_exists(self, mw, key_parts, ttl=None):
        key = mw.key(*key_parts)
        timestamp = yield mw.redis.get(key)
        self.assertTrue(timestamp, "Expected timestamp %r in Redis." % (key,))
        if ttl is not None:
            actual_ttl = yield mw.redis.ttl(key)
            self.assertTrue(
                0 <= actual_ttl <= ttl,
                "Expected ttl of %r to be less than %f, but got: %f" % (
                    key, ttl, actual_ttl))

    @inlineCallbacks
    def assert_no_redis_timestamp(self, mw, key_parts):
        key = mw.key(*key_parts)
        timestamp = yield mw.redis.get(key)
        self.assertEqual(
            timestamp, None, "Timestamp %r in Redis, expected none." % (key,))

    def assert_msg_timestamp_exists(self, mw, msg, transport_name):
        timestamp = mw._message_metadata(msg).get(transport_name)
        self.assertNotEqual(
            timestamp, None, "Expected timestamp in message metadata.")

    @inlineCallbacks
    def set_redis_timestamp(self, mw, dt, key_parts):
        key = mw.key(*key_parts)
        timestamp = time.time() + dt
        yield mw.redis.set(key, repr(timestamp))

    def set_msg_timestamp(self, mw, msg, dt, transport_name):
        timestamp = time.time() + dt
        mw._message_metadata(msg)[transport_name] = repr(timestamp)

    @inlineCallbacks
    def test_active_inbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg1 = self.mw_helper.make_inbound("foo", transport_name='endpoint_0')
        msg2 = self.mw_helper.make_inbound("foo", transport_name='endpoint_1')
        msg3 = self.mw_helper.make_inbound("foo", transport_name='endpoint_1')
        # The middleware inspects the message's transport_name value, not
        # the dispatcher endpoint it was received on.
        yield mw.handle_inbound(msg1, 'dummy_endpoint')
        yield mw.handle_inbound(msg2, 'dummy_endpoint')
        yield mw.handle_inbound(msg3, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'endpoint_0.inbound.counter': [1],
            'endpoint_1.inbound.counter': [1, 1],
        })

    @inlineCallbacks
    def test_passive_inbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg1 = self.mw_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg1, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.inbound.counter': [1],
        })

    @inlineCallbacks
    def test_active_outbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg1 = self.mw_helper.make_outbound("x", transport_name='endpoint_0')
        msg2 = self.mw_helper.make_outbound("x", transport_name='endpoint_1')
        msg3 = self.mw_helper.make_outbound("x", transport_name='endpoint_1')
        # The middleware inspects the message's transport_name value, not
        # the dispatcher endpoint it was received on.
        yield mw.handle_outbound(msg1, 'dummy_endpoint')
        yield mw.handle_outbound(msg2, 'dummy_endpoint')
        yield mw.handle_outbound(msg3, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'endpoint_0.outbound.counter': [1],
            'endpoint_1.outbound.counter': [1, 1],
        })

    @inlineCallbacks
    def test_passive_outbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg1 = self.mw_helper.make_outbound("x", transport_name='endpoint_0')
        yield mw.handle_outbound(msg1, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.outbound.counter': [1],
        })

    @inlineCallbacks
    def test_active_response_time_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg = self.mw_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_msg_timestamp_exists(mw, msg, 'endpoint_0')
        yield self.assert_no_redis_timestamp(
            mw, ['endpoint_0', msg['message_id']])

    @inlineCallbacks
    def test_passive_response_time_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mw_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_msg_timestamp_exists(mw, msg, 'dummy_endpoint')
        yield self.assert_no_redis_timestamp(
            mw, ['dummy_endpoint', msg['message_id']])

    @inlineCallbacks
    def test_active_response_time_comparison_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        inbound_msg = self.mw_helper.make_inbound(
            "foo", transport_name='endpoint_0')
        self.set_msg_timestamp(mw, inbound_msg, -10, 'endpoint_0')
        outbound_msg = inbound_msg.reply("bar")
        yield mw.handle_outbound(outbound_msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'endpoint_0.timer': {
                'values': (lambda v: v > 10),
                'aggs': ['avg', 'sum'],
            },
        })

    @inlineCallbacks
    def test_passive_response_time_comparison_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        inbound_msg = self.mw_helper.make_inbound(
            "foo", transport_name='endpoint_0')
        self.set_msg_timestamp(mw, inbound_msg, -10, 'dummy_endpoint')
        outbound_msg = inbound_msg.reply("bar")
        yield mw.handle_outbound(outbound_msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.timer': {
                'values': (lambda v: v > 10),
                'aggs': ['avg', 'sum'],
            },
        })

    @inlineCallbacks
    def test_sessions_started_on_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mw_helper.make_inbound(
            "foo", session_event=TransportUserMessage.SESSION_NEW)
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.sessions_started.counter': [1],
        })

    @inlineCallbacks
    def test_saving_session_start_timestamp_on_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mw_helper.make_inbound(
            "foo", session_event=TransportUserMessage.SESSION_NEW)
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        yield self.assert_redis_timestamp_exists(
            mw, ['dummy_endpoint', msg['to_addr']], ttl=600)

    @inlineCallbacks
    def test_session_close_on_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mw_helper.make_inbound(
            "foo", session_event=TransportUserMessage.SESSION_CLOSE)
        yield self.set_redis_timestamp(
            mw, -10, ['dummy_endpoint', msg['to_addr']])
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.session_time': {
                'values': (lambda v: v > 10),
                'aggs': ['avg', 'sum'],
            },
        })

    @inlineCallbacks
    def test_session_close_on_inbound_with_billing_unit(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'session_billing_unit': 50,
        })
        msg = self.mw_helper.make_inbound(
            "foo", session_event=TransportUserMessage.SESSION_CLOSE)
        yield self.set_redis_timestamp(
            mw, -10, ['dummy_endpoint', msg['to_addr']])
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.session_time': {
                'values': (lambda v: v > 10),
                'aggs': ['avg', 'sum'],
            },
            'dummy_endpoint.rounded.50s.session_time': {
                'values': (lambda v: v >= 50),
                'aggs': ['avg', 'sum'],
            },
        })

    @inlineCallbacks
    def test_sessions_started_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mw_helper.make_outbound(
            "foo", session_event=TransportUserMessage.SESSION_NEW)
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.sessions_started.counter': [1],
        })

    @inlineCallbacks
    def test_saving_session_start_timestamp_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mw_helper.make_outbound(
            "foo", session_event=TransportUserMessage.SESSION_NEW)
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        yield self.assert_redis_timestamp_exists(
            mw, ['dummy_endpoint', msg['from_addr']], ttl=600)

    @inlineCallbacks
    def test_session_close_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mw_helper.make_outbound(
            "foo", session_event=TransportUserMessage.SESSION_CLOSE)
        yield self.set_redis_timestamp(
            mw, -10, ['dummy_endpoint', msg['from_addr']])
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.session_time': {
                'values': (lambda v: v > 10),
                'aggs': ['avg', 'sum'],
            },
        })

    @inlineCallbacks
    def test_session_close_on_outbound_with_billing_unit(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'session_billing_unit': 50,
        })
        msg = self.mw_helper.make_outbound(
            "foo", session_event=TransportUserMessage.SESSION_CLOSE)
        yield self.set_redis_timestamp(
            mw, -10, ['dummy_endpoint', msg['from_addr']])
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.session_time': {
                'values': (lambda v: v > 10),
                'aggs': ['avg', 'sum'],
            },
            'dummy_endpoint.rounded.50s.session_time': {
                'values': (lambda v: v >= 50),
                'aggs': ['avg', 'sum'],
            },
        })

    @inlineCallbacks
    def test_provider_metrics_on_inbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'provider_metrics': True,
        })
        msg = self.mw_helper.make_inbound("foo", provider="MYMNO")
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.provider.mymno.inbound.counter': [1],
            'dummy_endpoint.inbound.counter': [1],
        })

    @inlineCallbacks
    def test_unknown_provider_metrics_on_inbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'provider_metrics': True,
        })
        msg = self.mw_helper.make_inbound("foo")
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.provider.unknown.inbound.counter': [1],
            'dummy_endpoint.inbound.counter': [1],
        })

    @inlineCallbacks
    def test_provider_metrics_on_outbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'provider_metrics': True,
        })
        msg = self.mw_helper.make_outbound("foo", provider="MYMNO")
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.provider.mymno.outbound.counter': [1],
            'dummy_endpoint.outbound.counter': [1],
        })

    @inlineCallbacks
    def test_unknown_provider_metrics_on_outbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'provider_metrics': True,
        })
        msg = self.mw_helper.make_outbound("foo")
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.provider.unknown.outbound.counter': [1],
            'dummy_endpoint.outbound.counter': [1],
        })

    @inlineCallbacks
    def test_tagpool_metrics_on_inbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'tagpools': {
                'mypool': {'track_pool': True},
            },
        })
        msg = self.mw_helper.make_inbound("foo", provider="MYMNO")
        TaggingMiddleware.add_tag_to_msg(msg, ("mypool", "tagA"))
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.tagpool.mypool.inbound.counter': [1],
            'dummy_endpoint.inbound.counter': [1],
        })

    @inlineCallbacks
    def test_tagpool_metrics_on_outbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'tagpools': {
                'mypool': {'track_pool': True},
            },
        })
        msg = self.mw_helper.make_outbound("foo")
        TaggingMiddleware.add_tag_to_msg(msg, ("mypool", "tagA"))
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.tagpool.mypool.outbound.counter': [1],
            'dummy_endpoint.outbound.counter': [1],
        })

    @inlineCallbacks
    def test_track_all_tags_metrics_on_inbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'tagpools': {
                'mypool': {'track_all_tags': True},
            },
        })
        msg = self.mw_helper.make_inbound("foo", provider="MYMNO")
        TaggingMiddleware.add_tag_to_msg(msg, ("mypool", "tagA"))
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.tag.mypool.taga.inbound.counter': [1],
            'dummy_endpoint.inbound.counter': [1],
        })

    @inlineCallbacks
    def test_track_all_tags_metrics_on_outbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'tagpools': {
                'mypool': {'track_all_tags': True},
            },
        })
        msg = self.mw_helper.make_outbound("foo")
        TaggingMiddleware.add_tag_to_msg(msg, ("mypool", "tagA"))
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.tag.mypool.taga.outbound.counter': [1],
            'dummy_endpoint.outbound.counter': [1],
        })

    @inlineCallbacks
    def test_track_specific_tag_on_inbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'tagpools': {
                'mypool': {'tags': ['tagC', 'tagD']},
            },
        })
        msg = self.mw_helper.make_inbound("foo", provider="MYMNO")
        TaggingMiddleware.add_tag_to_msg(msg, ("mypool", "tagC"))
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.tag.mypool.tagc.inbound.counter': [1],
            'dummy_endpoint.inbound.counter': [1],
        })

    @inlineCallbacks
    def test_track_specific_tag_on_outbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'tagpools': {
                'mypool': {'tags': ['tagC', 'tagD']},
            },
        })
        msg = self.mw_helper.make_outbound("foo")
        TaggingMiddleware.add_tag_to_msg(msg, ("mypool", "tagC"))
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.tag.mypool.tagc.outbound.counter': [1],
            'dummy_endpoint.outbound.counter': [1],
        })

    @inlineCallbacks
    def test_slugify_tagname(self):
        mw = yield self.get_middleware({})
        self.assertEqual(mw.slugify_tagname("*123"), "123")
        self.assertEqual(mw.slugify_tagname("*#123"), "123")
        self.assertEqual(mw.slugify_tagname("123!"), "123")
        self.assertEqual(mw.slugify_tagname("123!+"), "123")
        self.assertEqual(mw.slugify_tagname("1*23"), "1.23")
        self.assertEqual(mw.slugify_tagname("1*!23"), "1.23")
        self.assertEqual(mw.slugify_tagname("*12*3#"), "12.3")
        self.assertEqual(
            mw.slugify_tagname("foo@example.com"), "foo.example.com")

    @inlineCallbacks
    def test_slugify_tag_on_inbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'tagpools': {
                'mypool': {'tags': ['*123*456#']},
            },
        })
        msg = self.mw_helper.make_inbound("foo", provider="MYMNO")
        TaggingMiddleware.add_tag_to_msg(msg, ("mypool", "*123*456#"))
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.tag.mypool.123.456.inbound.counter': [1],
            'dummy_endpoint.inbound.counter': [1],
        })

    @inlineCallbacks
    def test_slugify_tag_on_outbound(self):
        mw = yield self.get_middleware({
            'op_mode': 'passive',
            'tagpools': {
                'mypool': {'tags': ['*123*567#']},
            },
        })
        msg = self.mw_helper.make_outbound("foo")
        TaggingMiddleware.add_tag_to_msg(msg, ("mypool", "*123*567#"))
        yield mw.handle_outbound(msg, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.tag.mypool.123.567.outbound.counter': [1],
            'dummy_endpoint.outbound.counter': [1],
        })

    @inlineCallbacks
    def test_ack_event(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        event = self.mw_helper.make_ack()
        mw.handle_event(event, 'dummy_endpoint')
        self.assert_metrics(mw, {
            'dummy_endpoint.event.ack.counter': [1],
        })

    @inlineCallbacks
    def test_delivery_report_event(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        for status in ['delivered', 'failed']:
            dr = self.mw_helper.make_delivery_report(delivery_status=status)
            mw.handle_event(dr, 'dummy_endpoint')

        def metric_name(status):
            return 'dummy_endpoint.event.delivery_report.%s.counter' % (
                status,)

        self.assert_metrics(mw, {
            metric_name('delivered'): [1],
            metric_name('failed'): [1],
        })

    @inlineCallbacks
    def test_failure(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        for failure in ['permanent', 'temporary', None]:
            fail_msg = FailureMessage(message='foo', failure_code=failure,
                                      reason='bar')
            mw.handle_failure(fail_msg, 'dummy_endpoint')

        def metric_name(status):
            return 'dummy_endpoint.failure.%s.counter' % (status,)

        self.assert_metrics(mw, {
            metric_name('permanent'): [1],
            metric_name('temporary'): [1],
            metric_name('unspecified'): [1],
        })

    @inlineCallbacks
    def test_session_max_lifetime(self):
        mw = yield self.get_middleware({'max_session_time': 10})
        msg1 = self.mw_helper.make_inbound(
            'foo', session_event=TransportUserMessage.SESSION_NEW)
        yield mw.handle_inbound(msg1, 'dummy_endpoint')
        yield self.assert_redis_timestamp_exists(
            mw, ['dummy_endpoint', msg1['to_addr']], ttl=10)

    @inlineCallbacks
    def test_metric_connectors_inbound_metrics_fired(self):
        mw = yield self.get_middleware({'metric_connectors': ['conn_1']})
        msg1 = self.mw_helper.make_inbound("foo")
        msg2 = yield mw.handle_inbound(msg1, 'conn_1')
        self.assert_metrics(mw, {
            'conn_1.inbound.counter': [1],
        })
        self.assertEqual(msg1, msg2)

    @inlineCallbacks
    def test_metric_connectors_inbound_metrics_not_fired(self):
        mw = yield self.get_middleware({'metric_connectors': ['conn_1']})
        msg1 = self.mw_helper.make_inbound("foo")
        msg2 = yield mw.handle_inbound(msg1, 'conn_2')
        self.assert_metrics_absent(mw, [
            'conn_2.inbound.counter',
        ])
        self.assertEqual(msg1, msg2)

    @inlineCallbacks
    def test_metric_connectors_outbound_fired(self):
        mw = yield self.get_middleware({'metric_connectors': ['conn_1']})
        msg1 = self.mw_helper.make_outbound("foo")
        msg2 = yield mw.handle_outbound(msg1, 'conn_1')
        self.assert_metrics(mw, {
            'conn_1.outbound.counter': [1],
        })
        self.assertEqual(msg1, msg2)

    @inlineCallbacks
    def test_metric_connectors_outbound_not_fired(self):
        mw = yield self.get_middleware({'metric_connectors': ['conn_1']})
        msg1 = self.mw_helper.make_outbound("foo")
        msg2 = yield mw.handle_outbound(msg1, 'conn_2')
        self.assert_metrics_absent(mw, [
            'conn_2.outbound.counter',
        ])
        self.assertEqual(msg1, msg2)

    @inlineCallbacks
    def test_metric_connectors_event_fired(self):
        mw = yield self.get_middleware({'metric_connectors': ['conn_1']})
        event1 = self.mw_helper.make_ack()
        event2 = mw.handle_event(event1, 'conn_1')
        self.assert_metrics(mw, {
            'conn_1.event.ack.counter': [1],
        })
        self.assertEqual(event1, event2)

    @inlineCallbacks
    def test_metric_connectors_event_not_fired(self):
        mw = yield self.get_middleware({'metric_connectors': ['conn_1']})
        event1 = self.mw_helper.make_ack()
        event2 = mw.handle_event(event1, 'conn_2')
        self.assert_metrics_absent(mw, [
            'conn_2.event.ack.counter',
        ])
        self.assertEqual(event1, event2)

    @inlineCallbacks
    def test_metric_connectors_failure_fired(self):
        mw = yield self.get_middleware({'metric_connectors': ['conn_1']})
        fail1 = FailureMessage(
            message='foo', failure_code='permanent', reason='bar')
        fail2 = mw.handle_failure(fail1, 'conn_1')
        self.assert_metrics(mw, {
            'conn_1.failure.permanent.counter': [1],
        })
        self.assertEqual(fail1, fail2)

    @inlineCallbacks
    def test_metric_connectors_failure_not_fired(self):
        mw = yield self.get_middleware({'metric_connectors': ['conn_1']})
        fail1 = FailureMessage(
            message='foo', failure_code='permanent', reason='bar')
        fail2 = mw.handle_failure(fail1, 'conn_2')
        self.assert_metrics_absent(mw, [
            'conn_2.failure.permanent.counter',
        ])
        self.assertEqual(fail1, fail2)


def collect_all_results(index_page, results=None):
    if results is None:
        results = []
    if index_page is None:
        return results
    results.extend(index_page)
    return index_page.next_page().addCallback(collect_all_results, results)


class TestConversationStoringMiddleware(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.mw_helper = self.add_helper(
            MiddlewareHelper(ConversationStoringMiddleware))
        yield self.mw_helper.setup_vumi_api()
        self.user_helper = yield self.mw_helper.make_user(u'user')
        self.conv = yield self.user_helper.create_conversation(u'dummy_conv')

    @inlineCallbacks
    def assert_stored_inbound(self, msgs):
        mdb = self.mw_helper.get_vumi_api().mdb
        index_page = yield mdb.batch_inbound_keys_page(self.conv.batch.key)
        ids = yield collect_all_results(index_page)
        self.assertEqual(sorted(ids), sorted(m['message_id'] for m in msgs))

    @inlineCallbacks
    def assert_stored_outbound(self, msgs):
        mdb = self.mw_helper.get_vumi_api().mdb
        index_page = yield mdb.batch_outbound_keys_page(self.conv.batch.key)
        ids = yield collect_all_results(index_page)
        self.assertEqual(sorted(ids), sorted(m['message_id'] for m in msgs))

    @inlineCallbacks
    def test_conversation_cache_ttl_config(self):
        """
        The conversation_cache_ttl config option is passed to the cache.
        """
        # When the config isn't provided, we use the default.
        mw = yield self.mw_helper.create_middleware()
        self.assertEqual(mw._conversation_cache._ttl, 5)
        mw2 = yield self.mw_helper.create_middleware(
            {"conversation_cache_ttl": 0})
        self.assertEqual(mw2._conversation_cache._ttl, 0)

    @inlineCallbacks
    def test_inbound_message(self):
        mw = yield self.mw_helper.create_middleware()

        msg1 = self.mw_helper.make_inbound("inbound", conv=self.conv)
        yield mw.handle_consume_inbound(msg1, 'default')
        yield self.assert_stored_inbound([msg1])

        msg2 = self.mw_helper.make_inbound("inbound", conv=self.conv)
        yield mw.handle_publish_inbound(msg2, 'default')
        yield self.assert_stored_inbound([msg1, msg2])

    @inlineCallbacks
    def test_inbound_message_no_consume_store(self):
        mw = yield self.mw_helper.create_middleware({
            'store_on_consume': False,
        })

        msg1 = self.mw_helper.make_inbound("inbound", conv=self.conv)
        yield mw.handle_consume_inbound(msg1, 'default')
        yield self.assert_stored_inbound([])

        msg2 = self.mw_helper.make_inbound("inbound", conv=self.conv)
        yield mw.handle_publish_inbound(msg2, 'default')
        yield self.assert_stored_inbound([msg2])

    @inlineCallbacks
    def test_outbound_message(self):
        mw = yield self.mw_helper.create_middleware()

        msg1 = self.mw_helper.make_outbound("outbound", conv=self.conv)
        yield mw.handle_consume_outbound(msg1, 'default')
        yield self.assert_stored_outbound([msg1])

        msg2 = self.mw_helper.make_outbound("outbound", conv=self.conv)
        yield mw.handle_publish_outbound(msg2, 'default')
        yield self.assert_stored_outbound([msg1, msg2])

    @inlineCallbacks
    def test_outbound_message_no_consume_store(self):
        mw = yield self.mw_helper.create_middleware({
            'store_on_consume': False,
        })

        msg1 = self.mw_helper.make_outbound("outbound", conv=self.conv)
        yield mw.handle_consume_outbound(msg1, 'default')
        yield self.assert_stored_outbound([])

        msg2 = self.mw_helper.make_outbound("outbound", conv=self.conv)
        yield mw.handle_publish_outbound(msg2, 'default')
        yield self.assert_stored_outbound([msg2])

    @inlineCallbacks
    def test_conversation_cached_for_inbound_message(self):
        """
        When we process an inbound message, the conversation lookup is cached.
        """
        mw = yield self.mw_helper.create_middleware()
        cache = mw._conversation_cache

        self.assertEqual(cache._models.keys(), [])
        msg1 = self.mw_helper.make_inbound("inbound", conv=self.conv)
        yield mw.handle_consume_inbound(msg1, 'default')
        self.assertEqual(cache._models.keys(), [self.conv.key])

    @inlineCallbacks
    def test_conversation_cached_for_outbound_message(self):
        """
        When we process an outbound message, the conversation lookup is cached.
        """
        mw = yield self.mw_helper.create_middleware()
        cache = mw._conversation_cache

        self.assertEqual(cache._models.keys(), [])
        msg1 = self.mw_helper.make_outbound("outbound", conv=self.conv)
        yield mw.handle_consume_outbound(msg1, 'default')
        self.assertEqual(cache._models.keys(), [self.conv.key])


class TestRouterStoringMiddleware(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.mw_helper = self.add_helper(
            MiddlewareHelper(RouterStoringMiddleware))
        yield self.mw_helper.setup_vumi_api()
        self.user_helper = yield self.mw_helper.make_user(u'user')
        self.router = yield self.user_helper.create_router(u'dummy_conv')

    @inlineCallbacks
    def assert_stored_inbound(self, msgs):
        mdb = self.mw_helper.get_vumi_api().mdb
        index_page = yield mdb.batch_inbound_keys_page(self.router.batch.key)
        ids = yield collect_all_results(index_page)
        self.assertEqual(sorted(ids), sorted(m['message_id'] for m in msgs))

    @inlineCallbacks
    def assert_stored_outbound(self, msgs):
        mdb = self.mw_helper.get_vumi_api().mdb
        index_page = yield mdb.batch_outbound_keys_page(self.router.batch.key)
        ids = yield collect_all_results(index_page)
        self.assertEqual(sorted(ids), sorted(m['message_id'] for m in msgs))

    @inlineCallbacks
    def test_inbound_message(self):
        mw = yield self.mw_helper.create_middleware()

        msg1 = self.mw_helper.make_inbound("inbound", router=self.router)
        yield mw.handle_consume_inbound(msg1, 'default')
        yield self.assert_stored_inbound([msg1])

        msg2 = self.mw_helper.make_inbound("inbound", router=self.router)
        yield mw.handle_publish_inbound(msg2, 'default')
        yield self.assert_stored_inbound([msg1, msg2])

    @inlineCallbacks
    def test_inbound_message_no_consume_store(self):
        mw = yield self.mw_helper.create_middleware({
            'store_on_consume': False,
        })

        msg1 = self.mw_helper.make_inbound("inbound", router=self.router)
        yield mw.handle_consume_inbound(msg1, 'default')
        yield self.assert_stored_inbound([])

        msg2 = self.mw_helper.make_inbound("inbound", router=self.router)
        yield mw.handle_publish_inbound(msg2, 'default')
        yield self.assert_stored_inbound([msg2])

    @inlineCallbacks
    def test_outbound_message(self):
        mw = yield self.mw_helper.create_middleware()

        msg1 = self.mw_helper.make_outbound("outbound", router=self.router)
        yield mw.handle_consume_outbound(msg1, 'default')
        yield self.assert_stored_outbound([msg1])

        msg2 = self.mw_helper.make_outbound("outbound", router=self.router)
        yield mw.handle_publish_outbound(msg2, 'default')
        yield self.assert_stored_outbound([msg1, msg2])

    @inlineCallbacks
    def test_outbound_message_no_consume_store(self):
        mw = yield self.mw_helper.create_middleware({
            'store_on_consume': False,
        })

        msg1 = self.mw_helper.make_outbound("outbound", router=self.router)
        yield mw.handle_consume_outbound(msg1, 'default')
        yield self.assert_stored_outbound([])

        msg2 = self.mw_helper.make_outbound("outbound", router=self.router)
        yield mw.handle_publish_outbound(msg2, 'default')
        yield self.assert_stored_outbound([msg2])


class TestConversationMetricsMiddleware(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.mw_helper = self.add_helper(
            MiddlewareHelper(ConversationMetricsMiddleware))
        yield self.mw_helper.setup_vumi_api()
        self.user_helper = yield self.mw_helper.make_user(u'user')
        self.conv = yield self.user_helper.create_conversation(
            u'bulk_message', name=u'Test Conversation', started=True)

    @inlineCallbacks
    def assert_conv_key_stored(self, mw, msg):
        value = yield mw.redis.smembers(
            ConversationMetricsMiddleware.RECENT_CONV_KEY)
        conv_details = '{"account_key": "%s","conv_key": "%s"}' % \
            (self.conv.user_account.key, self.conv.key)
        self.assertTrue(conv_details in value)
        self.assertEqual(len(value), 1)
        self.assertIn(conv_details, mw.local_recent_convs)

    @inlineCallbacks
    def assert_conv_key_not_stored(self, mw):
        value = yield mw.redis.smembers(
            ConversationMetricsMiddleware.RECENT_CONV_KEY)
        self.assertSetEqual(value, set([]))
        self.assertSetEqual(mw.local_recent_convs, set([]))

    @inlineCallbacks
    def test_inbound_message(self):
        mw = yield self.mw_helper.create_middleware()
        msg_helper = GoMessageHelper(vumi_helper=self.mw_helper)
        yield self.assert_conv_key_not_stored(mw)

        [msg] = yield msg_helper.add_inbound_to_conv(self.conv, 1)
        yield mw.handle_inbound(msg, "conn_1")
        yield self.assert_conv_key_stored(mw, msg)

    @inlineCallbacks
    def test_outbound_message(self):
        mw = yield self.mw_helper.create_middleware()
        msg_helper = GoMessageHelper(vumi_helper=self.mw_helper)
        yield self.assert_conv_key_not_stored(mw)

        [msg] = yield msg_helper.add_outbound_to_conv(self.conv, 1)
        yield mw.handle_outbound(msg, "conn_1")
        yield self.assert_conv_key_stored(mw, msg)

    @inlineCallbacks
    def test_reset_local_recent_convs(self):
        mw = yield self.mw_helper.create_middleware()
        mw.local_recent_convs.update(["conv1", "conv2"])

        mw.reset_local_recent_convs()

        self.assertEqual(mw.local_recent_convs, set([]))
