# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import LogCatcher

from go.vumitools.api_worker import EventDispatcher, CommandDispatcher
from go.vumitools.api import VumiApiCommand, VumiApiEvent
from go.vumitools.handler import EventHandler, SendMessageCommandHandler
from go.vumitools.tests.utils import AppWorkerTestCase


class CommandDispatcherTestCase(AppWorkerTestCase):

    application_class = CommandDispatcher

    @inlineCallbacks
    def setUp(self):
        super(CommandDispatcherTestCase, self).setUp()
        self.api = yield self.get_application({
                'worker_names': ['worker_1', 'worker_2']})

    def publish_command(self, cmd):
        return self.dispatch(cmd, rkey='vumi.api')

    @inlineCallbacks
    def test_forwarding_to_worker_name(self):
        api_cmd = VumiApiCommand.command('worker_1', 'foo')
        yield self.publish_command(api_cmd)
        [dispatched] = self._amqp.get_messages('vumi', 'worker_1.control')
        self.assertEqual(dispatched, api_cmd)

    @inlineCallbacks
    def test_unknown_worker_name(self):
        with LogCatcher() as logs:
            yield self.publish_command(
                VumiApiCommand.command('no-worker', 'foo'))
            [error] = logs.errors
            self.assertTrue("No worker publisher available" in
                                error['message'][0])

    @inlineCallbacks
    def test_badly_constructed_command(self):
        with LogCatcher() as logs:
            yield self.publish_command(VumiApiCommand())
            [error] = logs.errors
            self.assertTrue("No worker publisher available" in
                                error['message'][0])


class ToyHandler(EventHandler):
    def setup_handler(self):
        self.handled_events = []

    def handle_event(self, event, handler_config):
        self.handled_events.append((event, handler_config))


class EventDispatcherTestCase(AppWorkerTestCase):

    application_class = EventDispatcher

    @inlineCallbacks
    def setUp(self):
        yield super(EventDispatcherTestCase, self).setUp()
        self.ed = yield self.get_application(self.mk_config({
            'event_handlers': {
                    'handler1': '%s.ToyHandler' % __name__,
                    'handler2': '%s.ToyHandler' % __name__,
                    },
        }))
        self.handler1 = self.ed.handlers['handler1']
        self.handler2 = self.ed.handlers['handler2']

    def publish_event(self, cmd):
        return self.dispatch(cmd, rkey='vumi.event')

    def mkevent(self, event_type, content, conv_key="conv_key",
                account_key="acct"):
        return VumiApiEvent.event(
            account_key, conv_key, event_type, content)

    @inlineCallbacks
    def test_handle_event(self):
        self.ed.account_config['acct'] = {
            ('conv_key', 'my_event'): [('handler1', {})]}
        event = self.mkevent("my_event", {"foo": "bar"})
        self.assertEqual([], self.handler1.handled_events)
        yield self.publish_event(event)
        self.assertEqual([(event, {})], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)

    @inlineCallbacks
    def test_handle_event_uncached(self):
        user_account = yield self.mk_user(self.ed.vumi_api, u'dbacct')
        user_account.event_handler_config = [
            [['conv_key', 'my_event'], [('handler1', {})]]
            ]
        yield user_account.save()
        event = self.mkevent(
            "my_event", {"foo": "bar"}, account_key=user_account.key)
        self.assertEqual([], self.handler1.handled_events)
        yield self.publish_event(event)
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
        event = self.mkevent("my_event", {"foo": "bar"})
        event2 = self.mkevent("other_event", {"foo": "bar"})
        self.assertEqual([], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)
        yield self.publish_event(event)
        yield self.publish_event(event2)
        self.assertEqual(
            [(event, {'animal': 'puppy'}), (event2, {'animal': 'kitten'})],
            self.handler1.handled_events)
        self.assertEqual([(event2, {})], self.handler2.handled_events)


class SendingEventDispatcherTestCase(AppWorkerTestCase):
    application_class = EventDispatcher

    @inlineCallbacks
    def setUp(self):
        yield super(SendingEventDispatcherTestCase, self).setUp()
        ed_config = self.mk_config({
                'event_handlers': {
                    'handler1': "%s.%s" % (
                        SendMessageCommandHandler.__module__,
                        SendMessageCommandHandler.__name__)
                    },
                })
        self.ed = yield self.get_application(ed_config)
        self.handler1 = self.ed.handlers['handler1']

    def publish_event(self, cmd):
        return self.dispatch(cmd, rkey='vumi.event')

    def mkevent(self, event_type, content, conv_key="conv_key",
                account_key="acct"):
        return VumiApiEvent.event(
            account_key, conv_key, event_type, content)

    @inlineCallbacks
    def test_handle_events(self):
        user_account = yield self.mk_user(self.ed.vumi_api, u'dbacct')
        yield user_account.save()

        yield self.ed.vumi_api.tpm.declare_tags([(u"pool", u"tag1")])
        yield self.ed.vumi_api.tpm.set_metadata(u"pool", {
            "transport_type": "other",
            "msg_options": {"transport_name": "other_transport"},
            })
        self.user_api = self.ed.vumi_api.get_user_api(user_account.key)
        yield self.add_tagpool_permission(u"pool")

        conversation = yield self.create_conversation(
            conversation_type=u'bulk_message', description=u'message',
            config={}, delivery_tag_pool=u'pool', delivery_class=u'sms')

        yield conversation.start()

        user_account.event_handler_config = [
            [[conversation.key, 'my_event'], [('handler1', {
                'worker_name': 'other_worker',
                'conversation_key': 'other_conv',
                })]]
            ]
        yield user_account.save()

        event = self.mkevent("my_event",
                {"to_addr": "12345", "content": "hello"},
                account_key=user_account.key,
                conv_key=conversation.key)
        yield self.publish_event(event)

        [start_cmd, hack_cmd, api_cmd] = self._amqp.get_messages('vumi',
                                                                 'vumi.api')
        self.assertEqual(start_cmd['command'], 'start')
        self.assertEqual(hack_cmd['command'], 'initial_action_hack')
        self.assertEqual(api_cmd['worker_name'], 'other_worker')
        self.assertEqual(api_cmd['kwargs']['command_data'], {
                'content': 'hello',
                'batch_id': conversation.batches.keys()[0],
                'to_addr': '12345',
                'msg_options': {
                    'transport_name': 'other_transport',
                    'helper_metadata': {
                        'go': {'user_account': user_account.key},
                        'tag': {'tag': ['pool', 'tag1']},
                        },
                    'transport_type': 'other',
                    'from_addr': 'tag1',
                    }})
