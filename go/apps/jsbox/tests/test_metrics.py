"""Tests for go.apps.jsbox.metrics."""

import mock

from twisted.trial.unittest import TestCase

from go.apps.jsbox.metrics import (
    MetricEvent, MetricEventError, MetricsResource)


class TestMetricEvent(TestCase):

    SUM = MetricEvent.AGGREGATORS['sum']

    def test_create(self):
        ev = MetricEvent('mystore', 'foo', 2.0, self.SUM)
        self.assertEqual(ev.store, 'mystore')
        self.assertEqual(ev.metric, 'foo')
        self.assertEqual(ev.value, 2.0)
        self.assertEqual(ev.agg, self.SUM)

    def test_eq(self):
        ev1 = MetricEvent('mystore', 'foo', 1.5, self.SUM)
        ev2 = MetricEvent('mystore', 'foo', 1.5, self.SUM)
        self.assertEqual(ev1, ev2)

    def test_neq(self):
        ev1 = MetricEvent('mystore', 'foo', 1.5, self.SUM)
        ev2 = MetricEvent('mystore', 'bar', 1.5, self.SUM)
        self.assertNotEqual(ev1, ev2)

    def test_from_command(self):
        ev = MetricEvent.from_command({'store': 'mystore', 'metric': 'foo',
                                       'value': 1.5, 'agg': 'sum'})
        self.assertEqual(ev, MetricEvent('mystore', 'foo', 1.5, self.SUM))

    def test_bad_store(self):
        self.assertRaises(MetricEventError, MetricEvent.from_command, {
                'store': 'foo bar', 'metric': 'foo', 'value': 1.5,
                'agg': 'sum'})

    def test_bad_metric(self):
        self.assertRaises(MetricEventError, MetricEvent.from_command, {
                'store': 'mystore', 'metric': 'foo bar', 'value': 1.5,
                'agg': 'sum'})

    def test_missing_metric(self):
        self.assertRaises(MetricEventError, MetricEvent.from_command, {
                'store': 'mystore', 'value': 1.5, 'agg': 'sum'})

    def test_bad_value(self):
        self.assertRaises(MetricEventError, MetricEvent.from_command, {
                'store': 'mystore', 'metric': 'foo', 'value': 'abc',
                'agg': 'sum'})

    def test_missing_value(self):
        self.assertRaises(MetricEventError, MetricEvent.from_command, {
                'store': 'mystore', 'metric': 'foo', 'agg': 'sum'})

    def test_bad_agg(self):
        self.assertRaises(MetricEventError, MetricEvent.from_command, {
                'store': 'mystore', 'metric': 'foo', 'value': 1.5,
                'agg': 'foo'})

    def test_missing_agg(self):
        self.assertRaises(MetricEventError, MetricEvent.from_command, {
                'store': 'mystore', 'metric': 'foo', 'value': 1.5})


class TestMetricsResource(TestCase):

    def setUp(self):
        self.conversation = mock.Mock()
        self.app_worker = mock.Mock()
        self.dummy_api = object()
        self.resource = MetricsResource("test", self.app_worker, {})
        self.app_worker.conversation_for_api = mock.Mock(
            return_value=self.conversation)

    def test_handle_fire(self):
        self.fail("Not implemented")
