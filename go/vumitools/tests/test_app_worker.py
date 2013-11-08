# -*- coding: utf-8 -*-

"""Tests for go.vumitools.app_worker."""

from twisted.internet.defer import inlineCallbacks

from go.base import utils as base_utils
from go.vumitools.app_worker import GoApplicationWorker
from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.tests.helpers import GoMessageHelper
from go.vumitools.metrics import ConversationMetric
from go.vumitools.conversation.definition import ConversationDefinitionBase


class DummyMetric(ConversationMetric):
    METRIC_NAME = 'dummy_metric'

    def get_value(self):
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


class TestGoApplicationWorker(AppWorkerTestCase):
    application_class = DummyApplication

    @inlineCallbacks
    def setUp(self):
        super(TestGoApplicationWorker, self).setUp()

        self.patch(
            base_utils,
            'get_conversation_definition',
            lambda conv_type, conv: DummyConversationDefinition(conv))

        self.config = self.mk_config({})
        self.app = yield self.get_application(self.config)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)

        self.conv = yield self.create_conversation()
        self.msg_helper = GoMessageHelper(self.vumi_api.mdb)

    @inlineCallbacks
    def test_message_not_processed_while_stopped(self):
        self.assertEqual([], self.app.msgs)
        msg = self.msg_helper.make_inbound("inbound")
        self.assertFalse(self.conv.running())
        yield self.dispatch_to_conv(msg, self.conv)
        self.assertEqual([], self.app.msgs)

    @inlineCallbacks
    def test_message_processed_while_running(self):
        self.assertEqual([], self.app.msgs)
        msg = self.msg_helper.make_inbound("inbound")
        yield self.start_conversation(self.conv)
        self.conv = yield self.user_api.get_wrapped_conversation(self.conv.key)
        self.assertTrue(self.conv.running())
        yield self.dispatch_to_conv(msg, self.conv)
        self.assertEqual([msg], self.app.msgs)

    @inlineCallbacks
    def test_event_not_processed_while_stopped(self):
        self.assertEqual([], self.app.events)
        event = self.msg_helper.make_ack()
        self.assertFalse(self.conv.running())
        yield self.dispatch_event_to_conv(event, self.conv)
        self.assertEqual([], self.app.events)

    @inlineCallbacks
    def test_event_processed_while_running(self):
        self.assertEqual([], self.app.events)
        event = self.msg_helper.make_ack()
        yield self.start_conversation(self.conv)
        self.conv = yield self.user_api.get_wrapped_conversation(self.conv.key)
        self.assertTrue(self.conv.running())
        yield self.dispatch_event_to_conv(event, self.conv)
        self.assertEqual([event], self.app.events)

    @inlineCallbacks
    def test_collect_metrics(self):
        yield self.start_conversation(self.conv)

        yield self.dispatch_command(
            'collect_metrics',
            conversation_key=self.conv.key,
            user_account_key=self.user_account.key)

        prefix = "campaigns.test-0-user.conversations.%s" % self.conv.key

        self.assertEqual(
            self.get_published_metrics(self.app),
            [("%s.dummy_metric" % prefix, 42)])
