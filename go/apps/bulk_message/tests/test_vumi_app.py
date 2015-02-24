# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks, returnValue, DeferredQueue
from twisted.internet.task import Clock

from vumi.components.window_manager import WindowManager
from vumi.message import TransportUserMessage
from vumi.tests.helpers import VumiTestCase

from go.apps.bulk_message.vumi_app import BulkMessageApplication
from go.apps.tests.helpers import AppWorkerHelper
from go.vumitools.api import VumiApiCommand


class TestBulkMessageApplication(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(
            AppWorkerHelper(BulkMessageApplication))

        # Patch the clock so we can control time
        self.clock = Clock()
        self.patch(WindowManager, 'get_clock', lambda _: self.clock)

        self.app = yield self.app_helper.get_app_worker({})
        self._setup_wait_for_window_monitor()

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
    def setup_conversation(self):
        group = yield self.app_helper.create_group_with_contacts(u'group', 2)
        conv = yield self.app_helper.create_conversation(groups=[group])
        returnValue(conv)

    @inlineCallbacks
    def get_opted_in_contacts(self, conversation):
        contacts = []
        for bunch in (yield conversation.get_opted_in_contact_bunches(None)):
            contacts.extend((yield bunch))
        returnValue(sorted(contacts, key=lambda c: c.msisdn))

    @inlineCallbacks
    def test_start(self):
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)

        # Force processing of messages
        yield self.app_helper.kick_delivery()

        # Go past the monitoring interval to ensure the window is
        # being worked through for delivery
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        # Force processing of messages again
        yield self.app_helper.kick_delivery()

        # Assert that we've sent no messages
        self.assertEqual([], self.app_helper.get_dispatched_outbound())

    @inlineCallbacks
    def test_consume_events(self):
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key
        yield self.app_helper.dispatch_command(
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
        yield self.app_helper.kick_delivery()
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        [msg1, msg2] = yield self.app_helper.get_dispatched_outbound()
        yield self.app_helper.store_outbound(
            conversation, TransportUserMessage(**msg1.payload))
        yield self.app_helper.store_outbound(
            conversation, TransportUserMessage(**msg2.payload))

        # We should have two in flight
        self.assertEqual(
            (yield self.app.window_manager.count_in_flight(window_id)), 2)

        # Create an ack and a nack for the messages
        yield self.app_helper.make_dispatch_ack(msg1)
        yield self.app_helper.make_dispatch_nack(msg2, nack_reason='unknown')

        # We should have zero in flight
        self.assertEqual(
            (yield self.app.window_manager.count_in_flight(window_id)), 0)

    @inlineCallbacks
    def test_bulk_send_command(self):
        """
        If we send a bulk message to a number of contacts, we send a message to
        the msisdn for each contact.
        """
        group = yield self.app_helper.create_group_with_contacts(u'group', 10)
        conversation = yield self.app_helper.create_conversation(
            groups=[group])
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key
        yield self.app_helper.dispatch_command(
            "bulk_send",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=False,
            content="hello world",
            delivery_class="sms",
            msg_options={},
        )
        yield self.app_helper.kick_delivery()
        self.clock.advance(self.app.monitor_interval + 1)

        contacts = yield self.get_opted_in_contacts(conversation)
        msgs = yield self.app_helper.wait_for_dispatched_outbound(10)
        contact_addrs = sorted([contact.msisdn for contact in contacts])
        msg_addrs = sorted([msg["to_addr"] for msg in msgs])
        self.assertEqual(contact_addrs, msg_addrs)

    @inlineCallbacks
    def test_send_message_command(self):
        msg_options = {
            'transport_name': self.app_helper.transport_name,
            'from_addr': '666666',
            'transport_type': 'sphex',
            'helper_metadata': {'foo': {'bar': 'baz'}},
        }
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key
        yield self.app_helper.dispatch_command(
            "send_message",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            command_data={
                "batch_id": batch_id,
                "to_addr": "123456",
                "content": "hello world",
                "msg_options": msg_options,
            })

        [msg] = yield self.app_helper.get_dispatched_outbound()
        self.assertEqual(msg.payload['to_addr'], "123456")
        self.assertEqual(msg.payload['from_addr'], "666666")
        self.assertEqual(msg.payload['content'], "hello world")
        self.assertEqual(
            msg.payload['transport_name'], self.app_helper.transport_name)
        self.assertEqual(msg.payload['transport_type'], "sphex")
        self.assertEqual(msg.payload['message_type'], "user_message")
        self.assertEqual(msg.payload['helper_metadata']['go'], {
            'user_account': conversation.user_account.key,
            'conversation_type': 'bulk_message',
            'conversation_key': conversation.key,
        })
        self.assertEqual(msg.payload['helper_metadata']['foo'],
                         {'bar': 'baz'})

    @inlineCallbacks
    def test_process_command_send_message_in_reply_to(self):
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key
        msg = yield self.app_helper.make_stored_inbound(conversation, "foo")
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
        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], msg['from_addr'])
        self.assertEqual(sent_msg['content'], 'foo')
        self.assertEqual(sent_msg['in_reply_to'], msg['message_id'])
