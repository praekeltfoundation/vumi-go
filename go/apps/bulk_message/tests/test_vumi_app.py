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
    def test_bulk_send_command_with_duplicates(self):
        """
        If we send a bulk message to a number of contacts, we send a message to
        the msisdn for each contact, even if we have duplicate msisdns.
        """
        group1 = yield self.app_helper.create_group_with_contacts(u'group1', 3)
        group2 = yield self.app_helper.create_group_with_contacts(u'group2', 5)
        conversation = yield self.app_helper.create_conversation(
            groups=[group1, group2])
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
        msgs = yield self.app_helper.wait_for_dispatched_outbound(8)
        contact_addrs = sorted([contact.msisdn for contact in contacts])
        # Make sure we have duplicate addresses.
        self.assertNotEqual(len(contact_addrs), len(set(contact_addrs)))
        msg_addrs = sorted([msg["to_addr"] for msg in msgs])
        self.assertEqual(contact_addrs, msg_addrs)

    @inlineCallbacks
    def test_bulk_send_command_with_duplicates_dedupe(self):
        """
        If we send a bulk message to a number of contacts, we send a message to
        the msisdn for each contact, unless we have already sent a message to
        that msisdn.
        """
        group1 = yield self.app_helper.create_group_with_contacts(u'group1', 3)
        group2 = yield self.app_helper.create_group_with_contacts(u'group2', 5)
        conversation = yield self.app_helper.create_conversation(
            groups=[group1, group2])
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key
        yield self.app_helper.dispatch_command(
            "bulk_send",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=True,
            content="hello world",
            delivery_class="sms",
            msg_options={},
        )
        yield self.app_helper.kick_delivery()
        self.clock.advance(self.app.monitor_interval + 1)

        contacts = yield self.get_opted_in_contacts(conversation)
        msgs = yield self.app_helper.wait_for_dispatched_outbound(5)
        contact_addrs = sorted([contact.msisdn for contact in contacts])
        msg_addrs = sorted([msg["to_addr"] for msg in msgs])
        self.assertNotEqual(contact_addrs, msg_addrs)
        self.assertEqual(sorted(set(contact_addrs)), msg_addrs)

    @inlineCallbacks
    def test_interrupted_bulk_send_command_with_duplicates(self):
        """
        If we interrupt a bulk message command and reprocess it, we skip any
        messages we have already sent.
        """
        # Replace send_message_via_window with one that we can break.
        send_message_via_window = self.app.send_message_via_window
        send_broken = DeferredQueue()
        messages_sent = [0]

        def breaking_send_message_via_window(*args, **kw):
            if messages_sent[0] >= 4:
                send_broken.put(None)
                raise Exception("oops")
            messages_sent[0] += 1
            return send_message_via_window(*args, **kw)

        self.app.send_message_via_window = breaking_send_message_via_window

        group1 = yield self.app_helper.create_group_with_contacts(u'group1', 3)
        group2 = yield self.app_helper.create_group_with_contacts(u'group2', 5)
        conversation = yield self.app_helper.create_conversation(
            groups=[group1, group2])
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key

        send_progress = yield self.app.get_send_progress(conversation)
        self.assertEqual(send_progress, None)

        command_params = dict(
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=False,
            content="hello world",
            delivery_class="sms",
            msg_options={},
        )
        # We don't yield here, because this message will break the consumer and
        # never be acked.
        self.app_helper.dispatch_command("bulk_send", **command_params)
        yield send_broken.get()
        # Tell the fake broken that we've handled this message, because the
        # now-broken consumer can't.
        self.app.control_consumer._in_progress -= 1
        self.app.control_consumer.channel.message_processed()
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        contacts = yield self.get_opted_in_contacts(conversation)
        contact_addrs = sorted([contact.msisdn for contact in contacts])
        # Make sure we have duplicate addresses.
        self.assertNotEqual(len(contact_addrs), len(set(contact_addrs)))

        msgs1 = yield self.app_helper.get_dispatched_outbound()
        msg_addrs1 = [msg["to_addr"] for msg in msgs1]
        self.assertEqual(len(msg_addrs1), 4)

        send_progress = yield self.app.get_send_progress(conversation)
        self.assertEqual(send_progress, sorted(c.key for c in contacts)[3])

        self.app_helper.clear_dispatched_outbound()
        # Now we undo the breaking patch, replace the broken command consumer,
        # and redeliver the command message.
        self.app.send_message_via_window = send_message_via_window
        yield self.app._go_setup_command_consumer(self.app.get_static_config())
        yield self.app_helper.dispatch_command("bulk_send", **command_params)
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        msgs2 = yield self.app_helper.get_dispatched_outbound()
        msg_addrs2 = [msg["to_addr"] for msg in msgs2]
        self.assertEqual(len(msg_addrs2), 4)

        msg_addrs = sorted(msg_addrs1 + msg_addrs2)
        self.assertEqual(contact_addrs, msg_addrs)

        send_progress = yield self.app.get_send_progress(conversation)
        self.assertEqual(send_progress, None)

    @inlineCallbacks
    def test_interrupted_bulk_send_command_with_duplicates_dedupe(self):
        """
        If we interrupt a bulk message command and reprocess it, we skip any
        messages we have already sent and also deduplicate correctly.
        """
        # Replace send_message_via_window with one that we can break.
        send_message_via_window = self.app.send_message_via_window
        send_broken = DeferredQueue()
        messages_sent = [0]

        def breaking_send_message_via_window(*args, **kw):
            if messages_sent[0] >= 4:
                send_broken.put(None)
                raise Exception("oops")
            messages_sent[0] += 1
            return send_message_via_window(*args, **kw)

        self.app.send_message_via_window = breaking_send_message_via_window

        group1 = yield self.app_helper.create_group_with_contacts(u'group1', 3)
        group2 = yield self.app_helper.create_group_with_contacts(u'group2', 5)
        conversation = yield self.app_helper.create_conversation(
            groups=[group1, group2])
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key

        send_progress = yield self.app.get_send_progress(conversation)
        self.assertEqual(send_progress, None)

        command_params = dict(
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=True,
            content="hello world",
            delivery_class="sms",
            msg_options={},
        )
        # We don't yield here, because this message will break the consumer and
        # never be acked.
        self.app_helper.dispatch_command("bulk_send", **command_params)
        yield send_broken.get()
        # Tell the fake broken that we've handled this message, because the
        # now-broken consumer can't.
        self.app.control_consumer._in_progress -= 1
        self.app.control_consumer.channel.message_processed()
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        contacts = yield self.get_opted_in_contacts(conversation)
        contact_addrs = sorted([contact.msisdn for contact in contacts])
        # Make sure we have duplicate addresses.
        self.assertNotEqual(len(contact_addrs), len(set(contact_addrs)))

        msgs1 = yield self.app_helper.get_dispatched_outbound()
        msg_addrs1 = [msg["to_addr"] for msg in msgs1]
        self.assertTrue(len(msg_addrs1) <= 4)

        send_progress = yield self.app.get_send_progress(conversation)
        self.assertTrue(send_progress >= sorted(c.key for c in contacts)[3])

        self.app_helper.clear_dispatched_outbound()
        # Now we undo the breaking patch, replace the broken command consumer,
        # and redeliver the command message.
        self.app.send_message_via_window = send_message_via_window
        yield self.app._go_setup_command_consumer(self.app.get_static_config())
        yield self.app_helper.dispatch_command("bulk_send", **command_params)
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        msgs2 = yield self.app_helper.get_dispatched_outbound()
        msg_addrs2 = [msg["to_addr"] for msg in msgs2]
        self.assertTrue(len(msg_addrs2) <= 3)

        msg_addrs = sorted(msg_addrs1 + msg_addrs2)
        self.assertEqual(sorted(set(contact_addrs)), msg_addrs)

        send_progress = yield self.app.get_send_progress(conversation)
        self.assertEqual(send_progress, None)

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
