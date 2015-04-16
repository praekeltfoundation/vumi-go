# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from uuid import uuid4

from twisted.internet.defer import (
    inlineCallbacks, returnValue, DeferredQueue, Deferred)
from twisted.internet.task import Clock

from vumi.components.window_manager import WindowManager
from vumi.message import TransportUserMessage
from vumi.tests.helpers import VumiTestCase

from go.apps.bulk_message.vumi_app import BulkMessageApplication
from go.apps.tests.helpers import AppWorkerHelper
from go.vumitools.api import VumiApiCommand


class BreakerError(Exception):
    """
    An exception we can flush without clearing other errors.
    """


class MessageSendBreaker(object):
    """
    A helper to break message sending during a bulk send.
    """

    def __init__(self, app, allow):
        self.app = app
        self.allow = allow
        self._send_message_via_window = self.app.send_message_via_window
        self._messages_sent = 0

    def patch_app(self):
        """
        Replace the original send method with our broken one.
        """
        self.app.send_message_via_window = self._broken_send

    def _broken_send(self, *args, **kw):
        """
        Send up to self.allow messages, then raise an exception.
        """
        if self._messages_sent >= self.allow:
            raise BreakerError("oops")
        self._messages_sent += 1
        return self._send_message_via_window(*args, **kw)


class MessageSendPauser(object):
    """
    A helper to pause message sending during a bulk send.
    """

    def __init__(self, app, allow):
        self.app = app
        self.allow = allow
        self._send_message_via_window = self.app.send_message_via_window
        self._messages_sent = 0
        self._pause_d = Deferred()
        self._resume_d = Deferred()

    def patch_app(self):
        """
        Replace the original send method with our pausing one.
        """
        self.app.send_message_via_window = self._pausing_send

    def wait_for_pause(self):
        """
        Wait for sends to be paused.
        """
        return self._pause_d

    def resume(self):
        """
        Resume sends.
        """
        self._resume_d.callback(None)

    @inlineCallbacks
    def _pausing_send(self, *args, **kw):
        """
        Send up to self.allow messages, then pause and wait to be resumed.
        """
        if self._messages_sent == self.allow:
            self._pause_d.callback(None)
            yield self._resume_d
        self._messages_sent += 1
        yield self._send_message_via_window(*args, **kw)


class TestBulkMessageApplication(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(
            AppWorkerHelper(BulkMessageApplication))

        # Patch the clock so we can control time
        self.clock = Clock()
        self.patch(WindowManager, 'get_clock', lambda _: self.clock)

        # Hackery to wait for the window manager on the app.
        self._wm_state = {
            'queue': DeferredQueue(),
            'expected': 0,
        }
        self.app = yield self.get_app_worker(extra_worker=False)

    @inlineCallbacks
    def get_app_worker(self, extra_worker=True):
        app = yield self.app_helper.get_app_worker(
            {}, extra_worker=extra_worker)

        orig = app.window_manager._monitor_windows

        @inlineCallbacks
        def monitor_wrapper(*args, **kw):
            self._wm_state['expected'] += 1
            yield orig(*args, **kw)
            self._wm_state['queue'].put(object())

        self.patch(app.window_manager, '_monitor_windows', monitor_wrapper)
        returnValue(app)

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
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        [msg1, msg2] = self.app_helper.get_dispatched_outbound()
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
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        contacts = yield self.get_opted_in_contacts(conversation)
        msgs = self.app_helper.get_dispatched_outbound()
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
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        contacts = yield self.get_opted_in_contacts(conversation)
        msgs = self.app_helper.get_dispatched_outbound()
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
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        contacts = yield self.get_opted_in_contacts(conversation)
        msgs = self.app_helper.get_dispatched_outbound()
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
        send_breaker = MessageSendBreaker(self.app, 4)
        send_breaker.patch_app()

        group1 = yield self.app_helper.create_group_with_contacts(u'group1', 3)
        group2 = yield self.app_helper.create_group_with_contacts(u'group2', 5)
        conversation = yield self.app_helper.create_conversation(
            groups=[group1, group2])
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key
        cmd_id = uuid4().get_hex()

        send_progress = yield self.app.get_send_progress(conversation, cmd_id)
        self.assertEqual(send_progress, None)

        command_params = dict(
            command_id=cmd_id,
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=False,
            content="hello world",
            delivery_class="sms",
            msg_options={},
        )
        yield self.app_helper.dispatch_command("bulk_send", **command_params)
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        contacts = yield self.get_opted_in_contacts(conversation)
        contact_addrs = sorted([contact.msisdn for contact in contacts])
        # Make sure we have duplicate addresses.
        self.assertNotEqual(len(contact_addrs), len(set(contact_addrs)))

        msgs1 = self.app_helper.get_dispatched_outbound()
        msg_addrs1 = [msg["to_addr"] for msg in msgs1]
        self.assertEqual(len(msg_addrs1), 4)

        send_progress = yield self.app.get_send_progress(conversation, cmd_id)
        self.assertEqual(send_progress, sorted(c.key for c in contacts)[3])

        self.app_helper.clear_dispatched_outbound()
        # Set up an unbroken worker to process the redelivered command and
        # redeliver the command.
        yield self.get_app_worker()
        yield self.app_helper.dispatch_command("bulk_send", **command_params)
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        msgs2 = self.app_helper.get_dispatched_outbound()
        msg_addrs2 = [msg["to_addr"] for msg in msgs2]
        self.assertEqual(len(msg_addrs2), 4)

        msg_addrs = sorted(msg_addrs1 + msg_addrs2)
        self.assertEqual(contact_addrs, msg_addrs)

        send_progress = yield self.app.get_send_progress(conversation, cmd_id)
        self.assertEqual(send_progress, None)

        self.flushLoggedErrors(BreakerError)

    @inlineCallbacks
    def test_interrupted_bulk_send_command_with_duplicates_dedupe(self):
        """
        If we interrupt a bulk message command and reprocess it, we skip any
        messages we have already sent and also deduplicate correctly.
        """
        # Replace send_message_via_window with one that we can break.
        send_breaker = MessageSendBreaker(self.app, 4)
        send_breaker.patch_app()

        group1 = yield self.app_helper.create_group_with_contacts(u'group1', 3)
        group2 = yield self.app_helper.create_group_with_contacts(u'group2', 5)
        conversation = yield self.app_helper.create_conversation(
            groups=[group1, group2])
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key
        cmd_id = uuid4().get_hex()

        send_progress = yield self.app.get_send_progress(conversation, cmd_id)
        self.assertEqual(send_progress, None)

        command_params = dict(
            command_id=cmd_id,
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=True,
            content="hello world",
            delivery_class="sms",
            msg_options={},
        )
        yield self.app_helper.dispatch_command("bulk_send", **command_params)
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        contacts = yield self.get_opted_in_contacts(conversation)
        contact_addrs = sorted([contact.msisdn for contact in contacts])
        # Make sure we have duplicate addresses.
        self.assertNotEqual(len(contact_addrs), len(set(contact_addrs)))

        msgs1 = self.app_helper.get_dispatched_outbound()
        msg_addrs1 = [msg["to_addr"] for msg in msgs1]
        self.assertTrue(len(msg_addrs1) <= 4)

        send_progress = yield self.app.get_send_progress(conversation, cmd_id)
        self.assertTrue(send_progress >= sorted(c.key for c in contacts)[3])

        self.app_helper.clear_dispatched_outbound()
        # Set up an unbroken worker to process the redelivered command and
        # redeliver the command.
        yield self.get_app_worker()
        yield self.app_helper.dispatch_command("bulk_send", **command_params)
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        msgs2 = self.app_helper.get_dispatched_outbound()
        msg_addrs2 = [msg["to_addr"] for msg in msgs2]
        self.assertTrue(len(msg_addrs2) <= 3)

        msg_addrs = sorted(msg_addrs1 + msg_addrs2)
        self.assertEqual(sorted(set(contact_addrs)), msg_addrs)

        send_progress = yield self.app.get_send_progress(conversation, cmd_id)
        self.assertEqual(send_progress, None)

        self.flushLoggedErrors(BreakerError)

    @inlineCallbacks
    def test_overlapping_bulk_send_commands(self):
        """
        If we send a second command before the first one finishes, both sets of
        messages are sent to all contacts.
        """
        # Replace send_message_via_window with one that we can pause.
        send_pauser1 = MessageSendPauser(self.app, 3)
        send_pauser1.patch_app()

        group = yield self.app_helper.create_group_with_contacts(u'group', 10)
        conversation = yield self.app_helper.create_conversation(
            groups=[group])
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key

        # We don't yield here, because we want to start sending the next
        # message before this one's finished.
        first_d = self.app_helper.dispatch_command(
            "bulk_send",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=False,
            content="hello 1",
            delivery_class="sms",
            msg_options={},
        )
        yield send_pauser1.wait_for_pause()
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        # We should have sent 3 messages from the first send.
        msgs = self.app_helper.get_dispatched_outbound()
        self.assertEqual(["hello 1"] * 3, [m["content"] for m in msgs])

        # Set up a second worker to process the second command.
        app2 = yield self.get_app_worker()
        send_pauser2 = MessageSendPauser(app2, 3)
        send_pauser2.patch_app()
        second_d = self.app_helper.dispatch_command(
            "bulk_send",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            dedupe=False,
            content="hello 2",
            delivery_class="sms",
            msg_options={},
        )
        # Manually kick the command dispatcher. It's still waiting for the
        # previous command to finish.
        self.app_helper.dispatch_commands_to_app()
        yield send_pauser2.wait_for_pause()
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        # Unpause and wait for commands to finish.
        send_pauser1.resume()
        send_pauser2.resume()
        yield first_d
        yield second_d
        # Have the window manager deliver the messages.
        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        contacts = yield self.get_opted_in_contacts(conversation)
        contact_addrs = sorted([contact.msisdn for contact in contacts])

        msgs = self.app_helper.get_dispatched_outbound()
        msg_addrs1 = [m["to_addr"] for m in msgs if m["content"] == "hello 1"]
        msg_addrs2 = [m["to_addr"] for m in msgs if m["content"] == "hello 2"]
        self.assertEqual(sorted(msg_addrs1), contact_addrs)
        self.assertEqual(sorted(msg_addrs2), contact_addrs)

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

        [msg] = self.app_helper.get_dispatched_outbound()
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

    @inlineCallbacks
    def test_send_bad_message(self):
        """
        If a message can't be sent, we log the error and continue.
        """
        old_send_to = self.app.send_to

        def patched_send_to(to_addr, content, endpoint=None, **kw):
            if to_addr is None:
                raise BreakerError("no address")
            return old_send_to(to_addr, content, endpoint=endpoint, **kw)
        self.patch(self.app, "send_to", patched_send_to)

        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        batch_id = conversation.batch.key
        window_id = self.app.get_window_id(conversation.key, batch_id)

        yield self.app.send_message_via_window(
            conversation, window_id, batch_id, "12345", {}, "message 1")
        yield self.app.send_message_via_window(
            conversation, window_id, batch_id, None, {}, "broken")
        yield self.app.send_message_via_window(
            conversation, window_id, batch_id, "12346", {}, "message 2")

        self.clock.advance(self.app.monitor_interval + 1)
        yield self.wait_for_window_monitor()

        [msg1, msg2] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(
            [msg1["content"], msg2["content"]], ["message 1", "message 2"])

        [err] = self.flushLoggedErrors(BreakerError)
        self.assertEqual(err.getErrorMessage(), "no address")
