# -*- coding: utf-8 -*-

"""Tests for go.vumitools.app_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.apps.tests.helpers import AppWorkerHelper
from go.vumitools import app_worker
from go.vumitools.app_worker import GoApplicationWorker
from go.vumitools.metrics import ConversationMetric
from go.vumitools.conversation.definition import ConversationDefinitionBase


class DummyMetric(ConversationMetric):
    METRIC_NAME = 'dummy_metric'

    def get_value(self, user_api):
        return 42


class DummyConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'dummy'

    metrics = (DummyMetric,)


class DummyApplication(GoApplicationWorker):
    worker_name = 'dummy_application'

    @inlineCallbacks
    def setup_application(self):
        yield super(DummyApplication, self).setup_application()
        self.msgs = []
        self.events = []
        # Set these to empty dictionaries because we're not interested
        # in using any of the helper functions at this point.
        self._event_handlers = {}
        self._session_handlers = {}

    @inlineCallbacks
    def consume_user_message(self, message):
        # Grab the message config so it can raise an exception if necessary.
        yield self.get_message_config(message)
        self.msgs.append(message)

    @inlineCallbacks
    def consume_unknown_event(self, event):
        # Grab the message config so it can raise an exception if necessary.
        yield self.get_message_config(event)
        self.events.append(event)


class TestGoApplicationWorker(VumiTestCase):
    application_class = DummyApplication

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(AppWorkerHelper(DummyApplication))

        self.patch(
            app_worker,
            'get_conversation_definition',
            lambda conv_type, conv: DummyConversationDefinition(conv))

        self.app = yield self.app_helper.get_app_worker({})
        self.conv = yield self.app_helper.create_conversation()

    @inlineCallbacks
    def test_message_not_processed_while_stopped(self):
        self.assertFalse(self.conv.running())
        self.assertEqual([], self.app.msgs)
        yield self.app_helper.make_dispatch_inbound("inbound", conv=self.conv)
        self.assertEqual([], self.app.msgs)

    @inlineCallbacks
    def test_message_processed_while_running(self):
        yield self.app_helper.start_conversation(self.conv)
        self.assertEqual([], self.app.msgs)
        msg = yield self.app_helper.make_dispatch_inbound(
            "inbound", conv=self.conv)
        self.assertEqual([msg], self.app.msgs)

    @inlineCallbacks
    def test_event_not_processed_while_stopped(self):
        self.assertFalse(self.conv.running())
        self.assertEqual([], self.app.events)
        yield self.app_helper.make_dispatch_ack(conv=self.conv)
        self.assertEqual([], self.app.events)

    @inlineCallbacks
    def test_event_processed_while_running(self):
        self.assertEqual([], self.app.events)
        yield self.app_helper.start_conversation(self.conv)
        ack = yield self.app_helper.make_dispatch_ack(conv=self.conv)
        self.assertEqual([ack], self.app.events)

    @inlineCallbacks
    def test_collect_metrics(self):
        yield self.app_helper.start_conversation(self.conv)

        self.assertEqual(self.app_helper.get_published_metrics(self.app), [])

        yield self.app_helper.dispatch_command(
            'collect_metrics',
            conversation_key=self.conv.key,
            user_account_key=self.conv.user_account.key)

        prefix = "go.campaigns.test-0-user.conversations.%s" % self.conv.key

        self.assertEqual(
            self.app_helper.get_published_metrics(self.app),
            [("%s.dummy_metric" % prefix, 42)])

    @inlineCallbacks
    def test_conversation_metric_publishing(self):
        yield self.app_helper.start_conversation(self.conv)

        self.assertEqual(self.app_helper.get_published_metrics(self.app), [])

        user_helper = self.app_helper.vumi_helper.get_user_helper(
            self.conv.user_account.key)
        yield self.app.publish_conversation_metrics(
            user_helper.user_api, self.conv.key)

        prefix = "go.campaigns.test-0-user.conversations.%s" % self.conv.key

        self.assertEqual(
            self.app_helper.get_published_metrics(self.app),
            [("%s.dummy_metric" % prefix, 42)])

    @inlineCallbacks
    def test_account_metric_publishing(self):
        yield self.app_helper.start_conversation(self.conv)

        self.assertEqual(self.app_helper.get_published_metrics(self.app), [])

        yield self.app.publish_account_metric(
            self.conv.user_account.key, 'some-store', 'some-metric', 42)

        self.assertEqual(
            self.app_helper.get_published_metrics(self.app),
            [("go.campaigns.test-0-user.stores.some-store.some-metric", 42)])
