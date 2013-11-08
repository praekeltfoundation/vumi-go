# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks, returnValue, DeferredQueue
from twisted.internet.task import Clock

from vumi.message import TransportUserMessage
from vumi.components.window_manager import WindowManager
from vumi.tests.utils import LogCatcher

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.api import VumiApiCommand
from go.apps.bulk_message.vumi_app import BulkMessageApplication
from go.vumitools.tests.helpers import GoMessageHelper


class TestBulkMessageApplication(AppWorkerTestCase):

    application_class = BulkMessageApplication

    @inlineCallbacks
    def setUp(self):
        super(TestBulkMessageApplication, self).setUp()

        # Patch the clock so we can control time
        self.clock = Clock()
        self.patch(WindowManager, 'get_clock', lambda _: self.clock)

        self.config = self.mk_config({})
        self.app = yield self.get_application(self.config)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)
        yield self.setup_tagpools()
        self._setup_wait_for_window_monitor()
        self.msg_helper = GoMessageHelper(self.user_api.api.mdb)

    def _setup_wait_for_window_monitor(self):
        # Hackery to wait for the window manager on the app.
        self._wm_state = {
            'queue': DeferredQueue(),
            'expected': 0,
        }
        orig = self.app.window_manager._monitor_windows

        @inlineCallbacks
        def monitor_wrapper(*args, **kw):
            self._wm_state['expected'] += 1
            yield orig(*args, **kw)
            self._wm_state['queue'].put(object())

        self.patch(
            self.app.window_manager, '_monitor_windows', monitor_wrapper)

    @inlineCallbacks
    def wait_for_window_monitor(self):
        while self._wm_state['expected'] > 0:
            yield self._wm_state['queue'].get()
            self._wm_state['expected'] -= 1

    @inlineCallbacks
    def setup_conversation(self, contact_count=2,
                           from_addr=u'+27831234567{0}'):
        user_api = self.user_api
        group = yield user_api.contact_store.new_group(u'test group')

        for i in range(contact_count):
            yield user_api.contact_store.new_contact(
                name=u'First', surname=u'Surname %s' % (i,),
                msisdn=from_addr.format(i), groups=[group])

        conversation = yield self.create_conversation(
            description=u'message')
        conversation.add_group(group)
        yield conversation.save()
        returnValue(conversation)

    @inlineCallbacks
    def get_opted_in_contacts(self, conversation):
        contacts = []
        for bunch in (yield conversation.get_opted_in_contact_bunches(None)):
            contacts.extend((yield bunch))
        returnValue(sorted(contacts, key=lambda c: c.msisdn))

    @inlineCallbacks
    def test_start(self):
        conversation = yield self.setup_conversation()
        yield self.start_conversation(conversation)

        # Force processing of messages
        yield self._amqp.kick_delivery()

        # Go past the monitoring interval to ensure the window is
        # being worked through for delivery
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        # Force processing of messages again
        yield self._amqp.kick_delivery()

        # Assert that we've sent no messages
        self.assertEqual([], (yield self.get_dispatched_messages()))

    @inlineCallbacks
    def test_consume_events(self):
        conversation = yield self.setup_conversation()
        yield self.start_conversation(conversation)
        batch_id = conversation.batch.key
        yield self.dispatch_command(
            "bulk_send",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=False,
            content="hello world",
            delivery_class="sms",
            msg_options={},
        )
        window_id = self.app.get_window_id(conversation.key, batch_id)
        yield self._amqp.kick_delivery()
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        [msg1, msg2] = yield self.get_dispatched_messages()
        yield self.msg_helper.store_outbound(
            conversation, TransportUserMessage(**msg1.payload))
        yield self.msg_helper.store_outbound(
            conversation, TransportUserMessage(**msg2.payload))

        # We should have two in flight
        self.assertEqual(
            (yield self.app.window_manager.count_in_flight(window_id)), 2)

        # Create an ack and a nack for the messages
        ack = self.msg_helper.make_ack(msg1)
        yield self.dispatch_event(ack)
        nack = self.msg_helper.make_nack(msg2, nack_reason='unknown')
        yield self.dispatch_event(nack)

        yield self._amqp.kick_delivery()

        # We should have zero in flight
        self.assertEqual(
            (yield self.app.window_manager.count_in_flight(window_id)), 0)

    @inlineCallbacks
    def test_send_message_command(self):
        msg_options = {
            'transport_name': 'sphex_transport',
            'from_addr': '666666',
            'transport_type': 'sphex',
            'helper_metadata': {'foo': {'bar': 'baz'}},
        }
        conversation = yield self.setup_conversation()
        yield self.start_conversation(conversation)
        batch_id = conversation.batch.key
        yield self.dispatch_command(
            "send_message",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            command_data={
                "batch_id": batch_id,
                "to_addr": "123456",
                "content": "hello world",
                "msg_options": msg_options,
            })

        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg.payload['to_addr'], "123456")
        self.assertEqual(msg.payload['from_addr'], "666666")
        self.assertEqual(msg.payload['content'], "hello world")
        self.assertEqual(msg.payload['transport_name'], "sphex_transport")
        self.assertEqual(msg.payload['transport_type'], "sphex")
        self.assertEqual(msg.payload['message_type'], "user_message")
        self.assertEqual(msg.payload['helper_metadata']['go'], {
            'user_account': self.user_account.key,
            'conversation_type': 'bulk_message',
            'conversation_key': conversation.key,
        })
        self.assertEqual(msg.payload['helper_metadata']['foo'],
                         {'bar': 'baz'})

    @inlineCallbacks
    def test_process_command_send_message_in_reply_to(self):
        conversation = yield self.setup_conversation()
        yield self.start_conversation(conversation)
        batch_id = conversation.batch.key
        msg = yield self.msg_helper.make_stored_inbound(conversation, "foo")
        command = VumiApiCommand.command(
            'worker', 'send_message',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            command_data={
                u'batch_id': batch_id,
                u'content': u'foo',
                u'to_addr': u'to_addr',
                u'msg_options': {
                    u'transport_name': u'smpp_transport',
                    u'in_reply_to': msg['message_id'],
                    u'transport_type': u'sms',
                    u'from_addr': u'default10080',
                },
            })
        yield self.app.consume_control_command(command)
        [sent_msg] = self.get_dispatched_messages()
        self.assertEqual(sent_msg['to_addr'], msg['from_addr'])
        self.assertEqual(sent_msg['content'], 'foo')
        self.assertEqual(sent_msg['in_reply_to'], msg['message_id'])

    @inlineCallbacks
    def test_collect_metrics(self):
        conv = yield self.create_conversation()
        yield self.start_conversation(conv)

        yield self.msg_helper.make_stored_outbound(conv, "out 1")
        yield self.msg_helper.make_stored_outbound(conv, "out 2")
        yield self.msg_helper.make_stored_inbound(conv, "in 2")

        yield self.dispatch_command(
            'collect_metrics', conversation_key=conv.key,
            user_account_key=self.user_account.key)

        prefix = "campaigns.test-0-user.conversations.%s" % conv.key

        self.assertEqual(
            self.get_published_metrics(self.app),
            [("%s.messages_sent" % prefix, 2),
             ("%s.messages_received" % prefix, 1)])

    @inlineCallbacks
    def test_reconcile_cache(self):
        conv = yield self.create_conversation()

        with LogCatcher() as logger:
            yield self.dispatch_command(
                'reconcile_cache', conversation_key='bogus key',
                user_account_key=self.user_account.key)

            yield self.dispatch_command(
                'reconcile_cache', conversation_key=conv.key,
                user_account_key=self.user_account.key)

            [err] = logger.errors
            [msg1, msg2] = [msg for msg in logger.messages()
                            if 'twisted.web.client' not in msg]
            self.assertTrue('Conversation does not exist: bogus key'
                                in err['message'][0])
            self.assertEqual('Reconciling cache for %s' % (conv.key,), msg1)
            self.assertEqual('Cache reconciled for %s' % (conv.key,), msg2)
