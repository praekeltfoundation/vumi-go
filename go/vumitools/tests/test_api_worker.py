# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase
from vumi.tests.utils import LogCatcher

from go.vumitools.api_worker import EventDispatcher, CommandDispatcher
from go.vumitools.api import VumiApiCommand, VumiApiEvent
from go.vumitools.handler import EventHandler, SendMessageCommandHandler
from go.vumitools.tests.helpers import VumiApiHelper


class TestCommandDispatcher(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = self.add_helper(
            VumiApiHelper(), setup_vumi_api=False)
        self.worker_helper = self.vumi_helper.get_worker_helper()
        self.api = yield self.worker_helper.get_worker(
            CommandDispatcher, self.vumi_helper.mk_config({
                'transport_name': 'this should not be an application worker',
                'worker_names': ['worker_1', 'worker_2'],
            }))

    def publish_command(self, worker_name, command, *args, **kw):
        cmd = VumiApiCommand.command(worker_name, command, *args, **kw)
        d = self.worker_helper.dispatch_raw('vumi.api', cmd)
        return d.addCallback(lambda _: cmd)

    def get_worker_commands(self, worker_name):
        return self.worker_helper.get_dispatched(
            'worker_1', 'control', VumiApiCommand)

    @inlineCallbacks
    def test_forwarding_to_worker_name(self):
        api_cmd = yield self.publish_command('worker_1', 'foo')
        [dispatched] = self.get_worker_commands('worker_1')
        self.assertEqual(dispatched, api_cmd)

    @inlineCallbacks
    def test_unknown_worker_name(self):
        with LogCatcher() as logs:
            yield self.publish_command('no-worker', 'foo')
            [error] = logs.errors
            self.assertTrue("No worker publisher available" in
                                error['message'][0])

    @inlineCallbacks
    def test_badly_constructed_command(self):
        with LogCatcher() as logs:
            yield self.worker_helper.dispatch_raw('vumi.api', VumiApiCommand())
            [error] = logs.errors
            self.assertTrue("No worker publisher available" in
                                error['message'][0])


class ToyHandler(EventHandler):
    def setup_handler(self):
        self.handled_events = []

    def handle_event(self, event, handler_config):
        self.handled_events.append((event, handler_config))


class TestEventDispatcher(VumiTestCase):

    application_class = EventDispatcher

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = self.add_helper(
            VumiApiHelper(), setup_vumi_api=False)
        self.worker_helper = self.vumi_helper.get_worker_helper()
        self.ed = yield self.worker_helper.get_worker(
            EventDispatcher, self.vumi_helper.mk_config({
                'transport_name': 'this should not be an application worker',
                'event_handlers': {
                    'handler1': '%s.ToyHandler' % __name__,
                    'handler2': '%s.ToyHandler' % __name__,
                },
            }))
        self.handler1 = self.ed.handlers['handler1']
        self.handler2 = self.ed.handlers['handler2']

    def publish_event(self, event_type, content, conv_key="conv_key",
                      account_key="acct"):
        event = VumiApiEvent.event(account_key, conv_key, event_type, content)
        d = self.worker_helper.dispatch_raw('vumi.event', event)
        return d.addCallback(lambda _: event)

    @inlineCallbacks
    def test_handle_event(self):
        self.ed.account_config['acct'] = {
            ('conv_key', 'my_event'): [('handler1', {})]}
        self.assertEqual([], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)
        event = yield self.publish_event("my_event", {"foo": "bar"})
        self.assertEqual([(event, {})], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)

    @inlineCallbacks
    def test_handle_event_uncached(self):
        yield self.vumi_helper.setup_vumi_api()
        user_helper = yield self.vumi_helper.make_user(u'dbacct')
        user_account = yield user_helper.get_user_account()
        user_account.event_handler_config = [
            [['conv_key', 'my_event'], [('handler1', {})]]
        ]
        yield user_account.save()
        self.assertEqual([], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)
        event = yield self.publish_event(
            "my_event", {"foo": "bar"}, account_key=user_account.key)
        self.assertEqual([(event, {})], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)

    @inlineCallbacks
    def test_handle_events(self):
        self.ed.account_config['acct'] = {
            ('conv_key', 'my_event'): [('handler1', {'animal': 'puppy'})],
            ('conv_key', 'other_event'): [
                ('handler1', {'animal': 'kitten'}),
                ('handler2', {})
            ],
        }
        self.assertEqual([], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)
        event = yield self.publish_event("my_event", {"foo": "bar"})
        event2 = yield self.publish_event("other_event", {"foo": "bar"})
        self.assertEqual(
            [(event, {'animal': 'puppy'}), (event2, {'animal': 'kitten'})],
            self.handler1.handled_events)
        self.assertEqual([(event2, {})], self.handler2.handled_events)


class TestSendingEventDispatcher(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = self.add_helper(
            VumiApiHelper(), setup_vumi_api=False)
        self.worker_helper = self.vumi_helper.get_worker_helper()
        self.ed = yield self.worker_helper.get_worker(
            EventDispatcher, self.vumi_helper.mk_config({
                'transport_name': 'this should not be an application worker',
                'event_handlers': {
                    'handler1': "%s.%s" % (
                        SendMessageCommandHandler.__module__,
                        SendMessageCommandHandler.__name__)
                },
            }))

    def publish_event(self, event_type, content, conv_key="conv_key",
                      account_key="acct"):
        event = VumiApiEvent.event(account_key, conv_key, event_type, content)
        d = self.worker_helper.dispatch_raw('vumi.event', event)
        return d.addCallback(lambda _: event)

    @inlineCallbacks
    def test_handle_events(self):
        yield self.vumi_helper.setup_vumi_api()
        user_helper = yield self.vumi_helper.make_user(u'dbacct')
        user_account = yield user_helper.get_user_account()

        yield self.vumi_helper.setup_tagpool(u"pool", [u"tag1"], metadata={
            "transport_type": "other",
            "msg_options": {"transport_name": "other_transport"},
        })
        yield user_helper.add_tagpool_permission(u"pool")

        conversation = yield user_helper.create_conversation(
            u'bulk_message', description=u'message', config={}, started=True)

        user_account.event_handler_config = [
            [[conversation.key, 'my_event'], [('handler1', {
                'worker_name': 'other_worker',
                'conversation_key': 'other_conv',
            })]]
        ]
        yield user_account.save()

        yield self.publish_event(
            "my_event", {"to_addr": "12345", "content": "hello"},
            account_key=user_account.key, conv_key=conversation.key)

        [api_cmd] = self.vumi_helper.get_dispatched_commands()
        self.assertEqual(api_cmd['worker_name'], 'other_worker')
        self.assertEqual(api_cmd['kwargs']['command_data'], {
            'content': 'hello',
            'batch_id': conversation.batch.key,
            'to_addr': '12345',
            'msg_options': {
                'helper_metadata': {
                    'go': {'user_account': user_account.key},
                },
            }})
