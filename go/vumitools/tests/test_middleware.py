"""Tests for go.vumitools.middleware"""
import time

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.application.tests.test_base import DummyApplicationWorker

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.middleware import (NormalizeMsisdnMiddleware,
    OptOutMiddleware, MetricsMiddleware)


class MiddlewareTestCase(AppWorkerTestCase):

    application_class = DummyApplicationWorker

    @inlineCallbacks
    def setUp(self):
        yield super(MiddlewareTestCase, self).setUp()
        self.default_config = self.mk_config({})

    @inlineCallbacks
    def create_middleware(self, middleware_class, name='dummy_middleware',
                            config=None):
        dummy_worker = yield self.get_application({})
        mw = middleware_class(name, config or self.default_config,
                                dummy_worker)
        mw.setup_middleware()
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
    def setUp(self):
        yield super(MetricsMiddlewareTestCase, self).setUp()
        self.config = self.default_config.copy()
        self.config.update({
            'manager_name': 'metrics_manager',
            'count_suffix': 'counter',
            'response_time_suffix': 'timer',
            'redis_manager': {
                'FAKE_REDIS': 'yes please',
            }
        })
        self.mw = yield self.create_middleware(MetricsMiddleware,
            config=self.config)

    def tearDown(self):
        self.mw.teardown_middleware()

    @inlineCallbacks
    def test_inbound_counters(self):
        msg1 = self.mk_msg(transport_name='endpoint_0')
        msg2 = self.mk_msg(transport_name='endpoint_1')
        msg3 = self.mk_msg(transport_name='endpoint_1')
        # The middleware inspects the message's transport_name value, not
        # the dispatcher endpoint it was received on.
        yield self.mw.handle_inbound(msg1, 'dummy_endpoint')
        yield self.mw.handle_inbound(msg2, 'dummy_endpoint')
        yield self.mw.handle_inbound(msg3, 'dummy_endpoint')
        endpoint0_metric = self.mw.metric_manager['endpoint_0.inbound.counter']
        endpoint0_values = endpoint0_metric.poll()
        endpoint1_metric = self.mw.metric_manager['endpoint_1.inbound.counter']
        endpoint1_values = endpoint1_metric.poll()
        self.assertEqual(sum([m[1] for m in endpoint0_values]), 1)
        self.assertEqual(sum([m[1] for m in endpoint1_values]), 2)

    @inlineCallbacks
    def test_outbound_counters(self):
        msg1 = self.mk_msg(transport_name='endpoint_0')
        msg2 = self.mk_msg(transport_name='endpoint_1')
        msg3 = self.mk_msg(transport_name='endpoint_1')
        # The middleware inspects the message's transport_name value, not
        # the dispatcher endpoint it was received on.
        yield self.mw.handle_outbound(msg1, 'dummy_endpoint')
        yield self.mw.handle_outbound(msg2, 'dummy_endpoint')
        yield self.mw.handle_outbound(msg3, 'dummy_endpoint')
        endpoint0_metric = self.mw.metric_manager['endpoint_0.outbound.counter']
        endpoint0_values = endpoint0_metric.poll()
        endpoint1_metric = self.mw.metric_manager['endpoint_1.outbound.counter']
        endpoint1_values = endpoint1_metric.poll()
        self.assertEqual(sum([m[1] for m in endpoint0_values]), 1)
        self.assertEqual(sum([m[1] for m in endpoint1_values]), 2)

    @inlineCallbacks
    def test_response_time_inbound(self):
        msg = self.mk_msg(transport_name='endpoint_0')
        yield self.mw.handle_inbound(msg, 'dummy_endpoint')
        key = self.mw.key('endpoint_0', msg['message_id'])
        timestamp = yield self.mw.redis.get(key)
        self.assertTrue(timestamp)

    @inlineCallbacks
    def test_response_time_comparison_on_outbound(self):
        inbound_msg = self.mk_msg(transport_name='endpoint_0')
        key = self.mw.key('endpoint_0', inbound_msg['message_id'])
        # Fake it to be 10 seconds in the past
        timestamp = time.time() - 10
        yield self.mw.redis.set(key, repr(timestamp))
        outbound_msg = self.mk_msg(transport_name='endpoint_0',
            in_reply_to=inbound_msg['message_id'])
        yield self.mw.handle_outbound(outbound_msg, 'dummy_endpoint')
        [timer_metric] = self.mw.metric_manager['endpoint_0.timer'].poll()
        [timestamp, value] = timer_metric
        self.assertTrue(value > 10)
