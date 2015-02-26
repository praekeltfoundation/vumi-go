# -*- coding: utf-8 -*-

"""Tests for go.vumitools.app_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.connectors import IgnoreMessage
from vumi.tests.helpers import VumiTestCase
from vumi.tests.utils import LogCatcher

from go.apps.tests.helpers import AppWorkerHelper
from go.routers.tests.helpers import RouterWorkerHelper
from go.vumitools import app_worker
from go.vumitools.app_worker import GoApplicationWorker, GoRouterWorker
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
    def test_conversation_cache_ttl_config(self):
        """
        The conversation_cache_ttl config option is passed to the cache.
        """
        # When the config isn't provided, we use the default.
        self.assertEqual(self.app._conversation_cache._ttl, 5)

        app_helper2 = self.add_helper(AppWorkerHelper(DummyApplication))
        app2 = yield app_helper2.get_app_worker(
            {"conversation_cache_ttl": 0})
        self.assertEqual(app2._conversation_cache._ttl, 0)

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

    def test_control_queue_prefetch(self):
        self.assertEqual(self.app.control_consumer.prefetch_count, 1)

    @inlineCallbacks
    def test_command_ignored(self):
        yield self.app_helper.start_conversation(self.conv)

        def ignore_cmd_collect_metrics(cmd_id, conversation_key,
                                       user_account_key):
            raise IgnoreMessage("Ignoring message for conversation '%s'." % (
                conversation_key,))

        self.patch(
            self.app, 'process_command_collect_metrics',
            ignore_cmd_collect_metrics)

        self.assertEqual(self.app_helper.get_published_metrics(self.app), [])

        lc = LogCatcher()
        with lc:
            yield self.app_helper.dispatch_command(
                'collect_metrics',
                conversation_key=self.conv.key,
                user_account_key=self.conv.user_account.key)

        [logmsg] = lc.messages()
        self.assertTrue(logmsg.startswith("Ignoring msg due to IgnoreMessage"))
        self.assertEqual(self.app_helper.get_published_metrics(self.app), [])

    @inlineCallbacks
    def test_conversation_lookup_cached_start_command(self):
        """
        When we process a start command, the conversation lookup is cached.
        """
        cache = self.app._conversation_cache
        self.assertEqual(cache._models.keys(), [])
        yield self.app_helper.start_conversation(self.conv)
        self.assertEqual(cache._models.keys(), [self.conv.key])

    @inlineCallbacks
    def test_conversation_lookup_cached_for_message(self):
        """
        When we process a message, the conversation lookup is cached.
        """
        yield self.app_helper.start_conversation(self.conv)
        cache = self.app._conversation_cache
        cache.cleanup()
        self.assertEqual(cache._models.keys(), [])
        yield self.app_helper.make_dispatch_inbound("inbound", conv=self.conv)
        self.assertEqual(cache._models.keys(), [self.conv.key])

    @inlineCallbacks
    def test_conversation_lookup_cached_for_event(self):
        """
        When we process an event, the conversation lookup is cached.
        """
        yield self.app_helper.start_conversation(self.conv)
        cache = self.app._conversation_cache
        cache.cleanup()
        self.assertEqual(cache._models.keys(), [])
        yield self.app_helper.make_dispatch_ack(conv=self.conv)
        self.assertEqual(cache._models.keys(), [self.conv.key])


class DummyRouter(GoRouterWorker):
    worker_name = 'dummy_router'


class TestGoRouterWorker(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.rtr_helper = self.add_helper(RouterWorkerHelper(DummyRouter))

        self.patch(
            app_worker,
            'get_conversation_definition',
            lambda conv_type, conv: DummyConversationDefinition(conv))

        self.rtr_worker = yield self.rtr_helper.get_router_worker({})
        self.router = yield self.rtr_helper.create_router()

    @inlineCallbacks
    def assert_status(self, status):
        router = yield self.rtr_helper.get_router(self.router.key)
        self.assertEqual(router.status, status)

    @inlineCallbacks
    def test_start(self):
        yield self.assert_status('stopped')
        lc = LogCatcher()
        with lc:
            yield self.rtr_helper.start_router(self.router)
        self.assertEqual(lc.messages(), [
            u"Starting router '%s' for user 'test-0-user'." % self.router.key,
        ])
        yield self.assert_status('running')

    @inlineCallbacks
    def test_stop(self):
        yield self.rtr_helper.start_router(self.router)
        yield self.assert_status('running')
        lc = LogCatcher()
        with lc:
            yield self.rtr_helper.stop_router(self.router)
        self.assertEqual(lc.messages(), [
            u"Stopping router '%s' for user 'test-0-user'." % self.router.key,
        ])
        yield self.assert_status('stopped')

    @inlineCallbacks
    def test_handle_event(self):
        yield self.rtr_helper.start_router(self.router)

        outbound_hops = [
            [["CONVERSATION:dummy_conv:key", "default"],
             ["ROUTER:dummy_router:key", "endpoint1"]],
            [["ROUTER:dummy_router:key", "default"],
             ["TRANSPORT_TAG:pool:tag", "default"]],
        ]
        hops = outbound_hops[-1:]

        ack = yield self.rtr_helper.ri.make_dispatch_ack(
            router=self.router, hops=hops, outbound_hops=outbound_hops)
        [next_ack] = yield self.rtr_helper.ro.get_dispatched_events()
        self.assertEqual(next_ack.get_routing_endpoint(), "endpoint1")
        self.assertEqual(next_ack['user_message_id'], ack['user_message_id'])

    @inlineCallbacks
    def test_handle_event_no_next_hop(self):
        yield self.rtr_helper.start_router(self.router)

        outbound_hops = [
            [["ROUTER:dummy_router:key", "default"],
             ["TRANSPORT_TAG:pool:tag", "default"]],
        ]
        hops = outbound_hops[-1:]

        yield self.rtr_helper.ri.make_dispatch_ack(
            router=self.router, hops=hops, outbound_hops=outbound_hops)
        sent_events = yield self.rtr_helper.ro.get_dispatched_events()
        self.assertEqual(sent_events, [])

    @inlineCallbacks
    def test_command_ignored(self):
        yield self.rtr_helper.start_router(self.router)

        def ignore_cmd_collect_metrics(cmd_id, conversation_key,
                                       user_account_key):
            raise IgnoreMessage("Ignoring message for conversation '%s'." % (
                conversation_key,))

        self.patch(
            self.rtr_worker, 'process_command_collect_metrics',
            ignore_cmd_collect_metrics)

        lc = LogCatcher()
        with lc:
            yield self.rtr_helper.dispatch_command(
                'collect_metrics',
                conversation_key=self.router.key,
                user_account_key=self.router.user_account.key)

        [logmsg] = lc.messages()
        self.assertTrue(logmsg.startswith("Ignoring msg due to IgnoreMessage"))
