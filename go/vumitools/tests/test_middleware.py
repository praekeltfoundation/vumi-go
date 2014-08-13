"""Tests for go.vumitools.middleware"""
import time

from twisted.internet.defer import inlineCallbacks, returnValue

from zope.interface import implements

from vumi.transports.failures import FailureMessage
from vumi.middleware.tagger import TaggingMiddleware
from vumi.tests.helpers import VumiTestCase, generate_proxies, IHelper
from vumi.worker import BaseWorker

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin
from go.vumitools.middleware import (
    NormalizeMsisdnMiddleware, OptOutMiddleware, MetricsMiddleware,
    ConversationStoringMiddleware, RouterStoringMiddleware)
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

    def test_outbound_normalization(self):
        msg = self.mw_helper.make_outbound(
            "foo", to_addr='0123456789', from_addr='8007')
        msg = self.mw.handle_outbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['to_addr'], '+256123456789')


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
        endpoint0_metric = mw.metric_manager['endpoint_0.inbound.counter']
        endpoint0_values = endpoint0_metric.poll()
        endpoint1_metric = mw.metric_manager['endpoint_1.inbound.counter']
        endpoint1_values = endpoint1_metric.poll()
        self.assertEqual(sum([m[1] for m in endpoint0_values]), 1)
        self.assertEqual(sum([m[1] for m in endpoint1_values]), 2)

    @inlineCallbacks
    def test_passive_inbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg1 = self.mw_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg1, 'dummy_endpoint')
        [metric] = mw.metric_manager['dummy_endpoint.inbound.counter'].poll()
        self.assertEqual(metric[1], 1)

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
        endpoint0_metric = mw.metric_manager['endpoint_0.outbound.counter']
        endpoint0_values = endpoint0_metric.poll()
        endpoint1_metric = mw.metric_manager['endpoint_1.outbound.counter']
        endpoint1_values = endpoint1_metric.poll()
        self.assertEqual(sum([m[1] for m in endpoint0_values]), 1)
        self.assertEqual(sum([m[1] for m in endpoint1_values]), 2)

    @inlineCallbacks
    def test_passive_outbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg1 = self.mw_helper.make_outbound("x", transport_name='endpoint_0')
        yield mw.handle_outbound(msg1, 'dummy_endpoint')
        [metric] = mw.metric_manager['dummy_endpoint.outbound.counter'].poll()
        self.assertEqual(metric[1], 1)

    @inlineCallbacks
    def test_active_response_time_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg = self.mw_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        key = mw.key('endpoint_0', msg['message_id'])
        timestamp = yield mw.redis.get(key)
        self.assertTrue(timestamp)

    @inlineCallbacks
    def test_passive_response_time_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mw_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        key = mw.key('dummy_endpoint', msg['message_id'])
        timestamp = yield mw.redis.get(key)
        self.assertTrue(timestamp)

    @inlineCallbacks
    def test_active_response_time_comparison_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        inbound_msg = self.mw_helper.make_inbound(
            "foo", transport_name='endpoint_0')
        key = mw.key('endpoint_0', inbound_msg['message_id'])
        # Fake it to be 10 seconds in the past
        timestamp = time.time() - 10
        yield mw.redis.set(key, repr(timestamp))
        outbound_msg = inbound_msg.reply("bar")
        yield mw.handle_outbound(outbound_msg, 'dummy_endpoint')
        [timer_metric] = mw.metric_manager['endpoint_0.timer'].poll()
        [timestamp, value] = timer_metric
        self.assertTrue(value > 10)

    @inlineCallbacks
    def test_passive_response_time_comparison_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        inbound_msg = self.mw_helper.make_inbound(
            "foo", transport_name='endpoint_0')
        key = mw.key('dummy_endpoint', inbound_msg['message_id'])
        # Fake it to be 10 seconds in the past
        timestamp = time.time() - 10
        yield mw.redis.set(key, repr(timestamp))
        outbound_msg = inbound_msg.reply("bar")
        yield mw.handle_outbound(outbound_msg, 'dummy_endpoint')
        [timer_metric] = mw.metric_manager['dummy_endpoint.timer'].poll()
        [timestamp, value] = timer_metric
        self.assertTrue(value > 10)

    @inlineCallbacks
    def test_ack_event(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        event = self.mw_helper.make_ack()
        mw.handle_event(event, 'dummy_endpoint')
        [count] = mw.metric_manager['dummy_endpoint.event.ack.counter'].poll()
        self.assertEqual(count[1], 1)

    @inlineCallbacks
    def test_delivery_report_event(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        for status in ['delivered', 'failed']:
            dr = self.mw_helper.make_delivery_report(delivery_status=status)
            mw.handle_event(dr, 'dummy_endpoint')

        def metric_name(status):
            return 'dummy_endpoint.event.delivery_report.%s.counter' % (
                status,)

        [delivered] = mw.metric_manager[metric_name('delivered')].poll()
        [failed] = mw.metric_manager[metric_name('failed')].poll()
        self.assertEqual(delivered[1], 1)
        self.assertEqual(failed[1], 1)

    @inlineCallbacks
    def test_failure(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        for failure in ['permanent', 'temporary', None]:
            fail_msg = FailureMessage(message='foo', failure_code=failure,
                reason='bar')
            mw.handle_failure(fail_msg, 'dummy_endpoint')

        def metric_name(status):
            return 'dummy_endpoint.failure.%s.counter' % (status,)

        [permanent] = mw.metric_manager[metric_name('permanent')].poll()
        [temporary] = mw.metric_manager[metric_name('temporary')].poll()
        [unspecified] = mw.metric_manager[metric_name('unspecified')].poll()
        self.assertEqual(permanent[1], 1)
        self.assertEqual(temporary[1], 1)
        self.assertEqual(unspecified[1], 1)

    @inlineCallbacks
    def test_expiry(self):
        mw = yield self.get_middleware({'max_lifetime': 10})
        msg1 = self.mw_helper.make_inbound('foo', transport_name='endpoint_0')
        yield mw.handle_inbound(msg1, 'dummy_endpoint')
        key = mw.key('dummy_endpoint', msg1['message_id'])
        ttl = yield mw.redis.ttl(key)
        self.assertTrue(
            0 < ttl <= 10, "Expected 0 < ttl <= 10, found: %r" % (ttl,))


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
        ids = yield self.mw_helper.get_vumi_api().mdb.batch_inbound_keys(
            self.conv.batch.key)
        self.assertEqual(sorted(ids), sorted(m['message_id'] for m in msgs))

    @inlineCallbacks
    def assert_stored_outbound(self, msgs):
        ids = yield self.mw_helper.get_vumi_api().mdb.batch_outbound_keys(
            self.conv.batch.key)
        self.assertEqual(sorted(ids), sorted(m['message_id'] for m in msgs))

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
        ids = yield self.mw_helper.get_vumi_api().mdb.batch_inbound_keys(
            self.router.batch.key)
        self.assertEqual(sorted(ids), sorted(m['message_id'] for m in msgs))

    @inlineCallbacks
    def assert_stored_outbound(self, msgs):
        ids = yield self.mw_helper.get_vumi_api().mdb.batch_outbound_keys(
            self.router.batch.key)
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
