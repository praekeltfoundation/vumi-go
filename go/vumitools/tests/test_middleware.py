"""Tests for go.vumitools.middleware"""
import time

from twisted.internet.defer import inlineCallbacks, returnValue, maybeDeferred

from vumi.application.tests.test_base import DummyApplicationWorker
from vumi.transports.failures import FailureMessage
from vumi.middleware.tagger import TaggingMiddleware

from go.vumitools.tests.utils import AppWorkerTestCase, GoRouterWorkerTestMixin
from go.vumitools.middleware import (NormalizeMsisdnMiddleware,
    OptOutMiddleware, MetricsMiddleware, ConversationStoringMiddleware,
    RouterStoringMiddleware)
from go.vumitools.tests.helpers import GoMessageHelper


class MiddlewareTestCase(AppWorkerTestCase):

    application_class = DummyApplicationWorker

    @inlineCallbacks
    def setUp(self):
        yield super(MiddlewareTestCase, self).setUp()
        self.default_config = self.mk_config({})
        self._middlewares = []

    @inlineCallbacks
    def tearDown(self):
        for mw in self._middlewares:
            yield maybeDeferred(mw.teardown_middleware)
        yield super(MiddlewareTestCase, self).tearDown()

    @inlineCallbacks
    def create_middleware(self, middleware_class, name='dummy_middleware',
                          config=None):
        dummy_worker = yield self.get_application({})
        mw = middleware_class(
            name, config or self.default_config, dummy_worker)
        yield mw.setup_middleware()
        returnValue(mw)

    @inlineCallbacks
    def get_middleware(self, config=None, mw_class=MetricsMiddleware):
        default_config = self.mk_config({
            'manager_name': 'metrics_manager',
            'count_suffix': 'counter',
            'response_time_suffix': 'timer',
        })
        if config is not None:
            default_config.update(config)
        mw = yield self.create_middleware(MetricsMiddleware,
            config=default_config)
        self._middlewares.append(mw)
        returnValue(mw)


class NormalizeMisdnMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(NormalizeMisdnMiddlewareTestCase, self).setUp()
        self.mw = yield self.create_middleware(NormalizeMsisdnMiddleware,
            config={'country_code': '256'})
        self.msg_helper = GoMessageHelper()

    def test_normalization(self):
        msg = self.msg_helper.make_inbound(
            "foo", to_addr='8007', from_addr='256123456789')
        msg = self.mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['from_addr'], '+256123456789')


class OptOutMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(OptOutMiddlewareTestCase, self).setUp()
        self.config = self.default_config.copy()
        self.config.update({
            'optout_keywords': ['STOP', 'HALT', 'QUIT']
        })
        self.mw = yield self.create_middleware(OptOutMiddleware,
            config=self.config)
        yield self.mw.vumi_api.tpm.declare_tags([("pool", "tag1")])
        yield self.mw.vumi_api.tpm.set_metadata("pool", {
                "transport_type": "other",
                "msg_options": {"transport_name": "other_transport"},
                })
        self.msg_helper = GoMessageHelper(self.mw.vumi_api.mdb)

    @inlineCallbacks
    def send_keyword(self, mw, word, expected_response):
        msg = self.msg_helper.make_inbound(
            word, to_addr='to@domain.org', from_addr='from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, ("pool", "tag1"))
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        expected_response = dict(expected_response,
                                 tag={'tag': ['pool', 'tag1']})
        self.assertEqual(msg['helper_metadata'], expected_response)

    @inlineCallbacks
    def test_optout_flag(self):
        for keyword in self.config['optout_keywords']:
            yield self.send_keyword(self.mw, keyword, {
                'optout': {
                    'optout': True,
                    'optout_keyword': keyword.lower(),
                }
            })

    @inlineCallbacks
    def test_non_optout_keywords(self):
        for keyword in ['THESE', 'DO', 'NOT', 'OPT', 'OUT']:
            yield self.send_keyword(self.mw, keyword, {
                'optout': {
                    'optout': False,
                }
            })

    @inlineCallbacks
    def test_disabled_by_tagpool(self):
        yield self.mw.vumi_api.tpm.set_metadata("pool", {
                "transport_type": "other",
                "msg_options": {"transport_name": "other_transport"},
                "disable_global_opt_out": True,
                })
        yield self.send_keyword(self.mw, 'STOP', {
            'optout': {
                'optout': False,
            }
        })

    @inlineCallbacks
    def test_case_sensitivity(self):
        config = self.config.copy()
        config.update({
            'case_sensitive': True,
        })

        # This is a bit ugly. We get a new fakeredis here.
        mw = yield self.create_middleware(OptOutMiddleware, config=config)
        yield mw.vumi_api.tpm.declare_tags([("pool", "tag1")])
        yield mw.vumi_api.tpm.set_metadata("pool", {
                "transport_type": "other",
                "msg_options": {"transport_name": "other_transport"},
                })

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


class MetricsMiddlewareTestCase(MiddlewareTestCase):
    def setUp(self):
        self.msg_helper = GoMessageHelper()
        return super(MetricsMiddlewareTestCase, self).setUp()

    @inlineCallbacks
    def test_active_inbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg1 = self.msg_helper.make_inbound("foo", transport_name='endpoint_0')
        msg2 = self.msg_helper.make_inbound("foo", transport_name='endpoint_1')
        msg3 = self.msg_helper.make_inbound("foo", transport_name='endpoint_1')
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
        msg1 = self.msg_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg1, 'dummy_endpoint')
        [metric] = mw.metric_manager['dummy_endpoint.inbound.counter'].poll()
        self.assertEqual(metric[1], 1)

    @inlineCallbacks
    def test_active_outbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg1 = self.msg_helper.make_outbound("x", transport_name='endpoint_0')
        msg2 = self.msg_helper.make_outbound("x", transport_name='endpoint_1')
        msg3 = self.msg_helper.make_outbound("x", transport_name='endpoint_1')
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
        msg1 = self.msg_helper.make_outbound("x", transport_name='endpoint_0')
        yield mw.handle_outbound(msg1, 'dummy_endpoint')
        [metric] = mw.metric_manager['dummy_endpoint.outbound.counter'].poll()
        self.assertEqual(metric[1], 1)

    @inlineCallbacks
    def test_active_response_time_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg = self.msg_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        key = mw.key('endpoint_0', msg['message_id'])
        timestamp = yield mw.redis.get(key)
        self.assertTrue(timestamp)

    @inlineCallbacks
    def test_passive_response_time_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.msg_helper.make_inbound("foo", transport_name='endpoint_0')
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        key = mw.key('dummy_endpoint', msg['message_id'])
        timestamp = yield mw.redis.get(key)
        self.assertTrue(timestamp)

    @inlineCallbacks
    def test_active_response_time_comparison_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        inbound_msg = self.msg_helper.make_inbound(
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
        inbound_msg = self.msg_helper.make_inbound(
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
        event = self.msg_helper.make_ack()
        mw.handle_event(event, 'dummy_endpoint')
        [count] = mw.metric_manager['dummy_endpoint.event.ack.counter'].poll()
        self.assertEqual(count[1], 1)

    @inlineCallbacks
    def test_delivery_report_event(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        for status in ['delivered', 'failed']:
            dr = self.msg_helper.make_delivery_report(delivery_status=status)
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


class ConversationStoringMiddlewareTestCase(MiddlewareTestCase):
    @inlineCallbacks
    def setUp(self):
        yield super(ConversationStoringMiddlewareTestCase, self).setUp()
        self.mw = yield self.create_middleware(ConversationStoringMiddleware)
        self.vumi_api = self.mw.vumi_api  # yoink!
        yield self.setup_user_api(self.vumi_api)
        self.conv = yield self.create_conversation()
        self.msg_helper = GoMessageHelper(self.vumi_api.mdb)

    @inlineCallbacks
    def tearDown(self):
        yield self.mw.teardown_middleware()
        yield super(ConversationStoringMiddlewareTestCase, self).tearDown()

    @inlineCallbacks
    def test_inbound_message(self):
        msg = self.msg_helper.make_inbound("inbound", conv=self.conv)
        yield self.mw.handle_inbound(msg, 'default')
        batch_id = self.conv.batch.key
        msg_ids = yield self.vumi_api.mdb.batch_inbound_keys(batch_id)
        self.assertEqual(msg_ids, [msg['message_id']])

    @inlineCallbacks
    def test_outbound_message(self):
        msg = self.msg_helper.make_outbound("outbound", conv=self.conv)
        yield self.mw.handle_outbound(msg, 'default')
        batch_id = self.conv.batch.key
        msg_ids = yield self.vumi_api.mdb.batch_outbound_keys(batch_id)
        self.assertEqual(msg_ids, [msg['message_id']])


class RouterStoringMiddlewareTestCase(MiddlewareTestCase,
                                      GoRouterWorkerTestMixin):
    @inlineCallbacks
    def setUp(self):
        yield super(RouterStoringMiddlewareTestCase, self).setUp()
        self.mw = yield self.create_middleware(RouterStoringMiddleware)
        self.vumi_api = self.mw.vumi_api  # yoink!
        yield self.setup_user_api(self.vumi_api)
        self.router = yield self.create_router()
        self.msg_helper = GoMessageHelper(self.vumi_api.mdb)

    @inlineCallbacks
    def tearDown(self):
        yield self.mw.teardown_middleware()
        yield super(RouterStoringMiddlewareTestCase, self).tearDown()

    @inlineCallbacks
    def test_inbound_message(self):
        msg = self.msg_helper.make_inbound("inbound", router=self.router)
        yield self.mw.handle_inbound(msg, 'dummy_endpoint')
        msg_ids = yield self.vumi_api.mdb.batch_inbound_keys(
            self.router.batch.key)
        self.assertEqual(msg_ids, [msg['message_id']])

    @inlineCallbacks
    def test_outbound_message(self):
        msg = self.msg_helper.make_outbound("outbound", router=self.router)
        yield self.mw.handle_outbound(msg, 'dummy_endpoint')
        msg_ids = yield self.vumi_api.mdb.batch_outbound_keys(
            self.router.batch.key)
        self.assertEqual(msg_ids, [msg['message_id']])
