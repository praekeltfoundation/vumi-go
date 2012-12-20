"""Tests for go.apps.jsbox.metrics."""

import time
import json

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock, LoopingCall

from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.api import VumiApi

from go.apps.jsbox.metrics import MetricEvent, MetricStoreManager


class TestMetricEvent(TestCase):
    def test_to_json(self):
        now = time.time()
        ev = MetricEvent(event=MetricEvent.INC, store='default',
                         metric='my.metric', value=1.5, timestamp=now)
        self.assertEqual(ev.to_json(), json.dumps({
                'event': MetricEvent.INC, 'store': 'default',
                'metric': 'my.metric', 'value': 1.5,
                'timestamp': now
        }))

    def test_from_json(self):
        now = time.time()
        ev = MetricEvent.from_json(json.dumps({
                'event': MetricEvent.INC, 'store': 'default',
                'metric': 'my.metric', 'value': 1.5,
                'timestamp': now
        }))
        expected_ev = MetricEvent(event=MetricEvent.INC, store='default',
                                  metric='my.metric', value=1.5, timestamp=now)
        self.assertEqual(ev, expected_ev)


class TestMetricStoreManager(GoPersistenceMixin, TestCase):

    use_riak = True
    metric_interval = 300

    @inlineCallbacks
    def setUp(self):
        yield super(TestMetricStoreManager, self).setUp()
        yield self._persist_setUp()
        self.clock = Clock()
        self.patch(MetricStoreManager, 'looping_call',
                   self.looping_call)
        self.vumi_api = yield VumiApi.from_config_async(self.mk_config({}))
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.msm = MetricStoreManager(self.vumi_api, self.metric_interval)

    @inlineCallbacks
    def tearDown(self):
        yield super(TestMetricStoreManager, self).tearDown()
        yield self._persist_tearDown()
        yield self.msm.stop()

    def looping_call(self, *args, **kw):
        lc = LoopingCall(*args, **kw)
        lc.clock = self.clock
        return lc

    def test_store_id(self):
        self.assertEqual(self.msm.store_id("12345", "default"),
                         "12345:default")

    def test_parse_store_id(self):
        self.assertEqual(self.msm.parse_store_id("12345:default"),
                         ("12345", "default"))
