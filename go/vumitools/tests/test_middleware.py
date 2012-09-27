"""Tests for go.vumitools.middleware"""
import time

from twisted.internet.defer import inlineCallbacks, returnValue, maybeDeferred

from vumi.message import TransportUserMessage
from vumi.application.tests.test_base import DummyApplicationWorker
from vumi.transports.failures import FailureMessage

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.middleware import (NormalizeMsisdnMiddleware,
    OptOutMiddleware, MetricsMiddleware)


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

    @inlineCallbacks
    def create_middleware(self, middleware_class, name='dummy_middleware',
                            config=None):
        dummy_worker = yield self.get_application({})
        mw = middleware_class(name, config or self.default_config,
                                dummy_worker)
        mw.setup_middleware()
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

    def mk_msg(self, **kwargs):
        defaults = {
            'to_addr': 'to@addr.com',
            'from_addr': 'from@addr.com',
            'transport_name': 'dummy_endpoint',
            'transport_type': 'dummy_transport_type',
        }
        defaults.update(kwargs)
        return TransportUserMessage(**defaults)


class NormalizeMisdnMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(NormalizeMisdnMiddlewareTestCase, self).setUp()
        self.mw = yield self.create_middleware(NormalizeMsisdnMiddleware,
            config={'country_code': '256'})

    def test_normalization(self):
        msg = self.mk_msg(to_addr='8007', from_addr='256123456789')
        msg = self.mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['from_addr'], '+256123456789')


class OptOutMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(OptOutMiddlewareTestCase, self).setUp()
        self.config = self.default_config.copy()
        self.config.update({
            'keyword_separator': '-',
            'optout_keywords': ['STOP', 'HALT', 'QUIT']
        })
        self.mw = yield self.create_middleware(OptOutMiddleware,
            config=self.config)

    def send_keyword(self, mw, word, expected_response):
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        msg['content'] = '%s%sfoo' % (
            word, self.config['keyword_separator'])
        yield mw.handle_inbound(msg, 'dummy_endpoint')
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
    def test_case_sensitivity(self):
        config = self.config.copy()
        config.update({
            'case_sensitive': True,
        })
        mw = yield self.create_middleware(OptOutMiddleware, config=config)

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

    @inlineCallbacks
    def test_active_inbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg1 = self.mk_msg(transport_name='endpoint_0')
        msg2 = self.mk_msg(transport_name='endpoint_1')
        msg3 = self.mk_msg(transport_name='endpoint_1')
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
        msg1 = self.mk_msg(transport_name='endpoint_0')
        yield mw.handle_inbound(msg1, 'dummy_endpoint')
        [metric] = mw.metric_manager['dummy_endpoint.inbound.counter'].poll()
        self.assertEqual(metric[1], 1)

    @inlineCallbacks
    def test_active_outbound_counters(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg1 = self.mk_msg(transport_name='endpoint_0')
        msg2 = self.mk_msg(transport_name='endpoint_1')
        msg3 = self.mk_msg(transport_name='endpoint_1')
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
        msg1 = self.mk_msg(transport_name='endpoint_0')
        yield mw.handle_outbound(msg1, 'dummy_endpoint')
        [metric] = mw.metric_manager['dummy_endpoint.outbound.counter'].poll()
        self.assertEqual(metric[1], 1)

    @inlineCallbacks
    def test_active_response_time_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        msg = self.mk_msg(transport_name='endpoint_0')
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        key = mw.key('endpoint_0', msg['message_id'])
        timestamp = yield mw.redis.get(key)
        self.assertTrue(timestamp)

    @inlineCallbacks
    def test_passive_response_time_inbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        msg = self.mk_msg(transport_name='endpoint_0')
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        key = mw.key('dummy_endpoint', msg['message_id'])
        timestamp = yield mw.redis.get(key)
        self.assertTrue(timestamp)

    @inlineCallbacks
    def test_active_response_time_comparison_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'active'})
        inbound_msg = self.mk_msg(transport_name='endpoint_0')
        key = mw.key('endpoint_0', inbound_msg['message_id'])
        # Fake it to be 10 seconds in the past
        timestamp = time.time() - 10
        yield mw.redis.set(key, repr(timestamp))
        outbound_msg = self.mk_msg(transport_name='endpoint_0',
            in_reply_to=inbound_msg['message_id'])
        yield mw.handle_outbound(outbound_msg, 'dummy_endpoint')
        [timer_metric] = mw.metric_manager['endpoint_0.timer'].poll()
        [timestamp, value] = timer_metric
        self.assertTrue(value > 10)

    @inlineCallbacks
    def test_passive_response_time_comparison_on_outbound(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        inbound_msg = self.mk_msg(transport_name='endpoint_0')
        key = mw.key('dummy_endpoint', inbound_msg['message_id'])
        # Fake it to be 10 seconds in the past
        timestamp = time.time() - 10
        yield mw.redis.set(key, repr(timestamp))
        outbound_msg = self.mk_msg(transport_name='endpoint_0',
            in_reply_to=inbound_msg['message_id'])
        yield mw.handle_outbound(outbound_msg, 'dummy_endpoint')
        [timer_metric] = mw.metric_manager['dummy_endpoint.timer'].poll()
        [timestamp, value] = timer_metric
        self.assertTrue(value > 10)

    @inlineCallbacks
    def test_ack_event(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        event = self.mkmsg_ack()
        mw.handle_event(event, 'dummy_endpoint')
        [counter] = mw.metric_manager['dummy_endpoint.event.ack.counter'].poll()
        self.assertEqual(counter[1], 1)

    @inlineCallbacks
    def test_delivery_report_event(self):
        mw = yield self.get_middleware({'op_mode': 'passive'})
        for status in ['delivered', 'failed']:
            event = self.mkmsg_delivery(status=status)
            mw.handle_event(event, 'dummy_endpoint')

        def metric_name(status):
            return 'dummy_endpoint.event.delivery_report.%s.counter' % (status,)

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
