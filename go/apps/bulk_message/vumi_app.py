# -*- test-case-name: go.apps.bulk_message.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""
from twisted.internet.defer import inlineCallbacks

from vumi.components.window_manager import WindowManager
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker


SEND_PROGRESS_EXPIRY = 3600 * 24 * 7  # One week


class BulkMessageApplication(GoApplicationWorker):
    """
    Application that accepts 'send message' commands and does exactly that.
    """
    worker_name = 'bulk_message_application'
    max_ack_window = 100
    max_ack_wait = 100
    monitor_interval = 20
    monitor_window_cleanup = True

    @inlineCallbacks
    def setup_application(self):
        yield super(BulkMessageApplication, self).setup_application()
        wm_redis = self.redis.sub_manager('%s:window_manager' % (
            self.worker_name,))
        self.window_manager = WindowManager(
            wm_redis,
            window_size=self.max_ack_window,
            flight_lifetime=self.max_ack_wait)
        self.window_manager.monitor(
            self.on_window_key_ready,
            interval=self.monitor_interval,
            cleanup=self.monitor_window_cleanup,
            cleanup_callback=self.on_window_cleanup)

    @inlineCallbacks
    def teardown_application(self):
        yield super(BulkMessageApplication, self).teardown_application()
        self.window_manager.stop()

    @inlineCallbacks
    def on_window_key_ready(self, window_id, flight_key):
        data = yield self.window_manager.get_data(window_id, flight_key)
        to_addr = data['to_addr']
        content = data['content']
        msg_options = data['msg_options']
        try:
            msg = yield self.send_to(
                to_addr, content, endpoint='default', **msg_options)
        except Exception:
            # Log the error and move on.
            log.err()
        else:
            yield self.window_manager.set_external_id(
                window_id, flight_key, msg['message_id'])

    def on_window_cleanup(self, window_id):
        log.info('Finished window %s, removing.' % (window_id,))

    def get_window_id(self, conversation_key, batch_id):
        return ':'.join([conversation_key, batch_id])

    def _send_progress_key(self, conv, command_id):
        return ':'.join([self.worker_name, conv.key, command_id])

    def get_send_progress(self, conv, command_id):
        return self.redis.get(self._send_progress_key(conv, command_id))

    def set_send_progress(self, conv, command_id, contact_key):
        key = self._send_progress_key(conv, command_id)
        return self.redis.setex(key, SEND_PROGRESS_EXPIRY, contact_key)

    def clear_send_progress(self, conv, command_id):
        return self.redis.delete(self._send_progress_key(conv, command_id))

    @inlineCallbacks
    def send_message_via_window(self, conv, window_id, batch_id, to_addr,
                                msg_options, content):
        yield self.window_manager.create_window(window_id, strict=False)
        yield self.window_manager.add(window_id, {
            'batch_id': batch_id,
            'to_addr': to_addr,
            'content': content,
            'msg_options': msg_options,
            })

    @inlineCallbacks
    def process_command_bulk_send(self, cmd_id, user_account_key,
                                  conversation_key, batch_id, msg_options,
                                  content, dedupe, delivery_class,
                                  **extra_params):
        """
        Send a copy of a message to every contact in every group attached to
        a conversation.

        If this command is interrupted (by a worker restart, for example) the
        next time it is processed it will avoid sending the message to contacts
        that it has already been sent to. Note that the contact and opt-out
        lookups still happen (because those are required for deduplication), so
        there may be a lengthly delay before the remaining messages are sent if
        the previous send was interrupted after a large number of messages.
        """
        conv = yield self.get_conversation(user_account_key, conversation_key)
        if conv is None:
            log.warning("Cannot find conversation '%s' for user '%s'." % (
                conversation_key, user_account_key))
            return
        contact_store = conv.user_api.contact_store
        addresses_seen = set()  # To deduplicate addresses, if asked.

        # NOTE: We fetch all contact keys before we start. This is suboptimal,
        #       but we need the keys sorted and deduplicated.
        contact_keys = yield conv.get_contact_keys()
        contact_keys.sort()  # Sort in-place to keep memory usage down.

        self.add_conv_to_msg_options(conv, msg_options)
        window_id = self.get_window_id(conversation_key, batch_id)
        interrupted_progress = yield self.get_send_progress(conv, cmd_id)
        if interrupted_progress is not None:
            log.warning(
                "Resuming interrupted send for conversation '%s' at '%s'." % (
                    conv.key, interrupted_progress))

        for contact_key in contact_keys:
            contact = yield contact_store.get_contact_by_key(contact_key)
            to_addr = yield conv.get_opted_in_contact_address(
                contact, delivery_class)
            if dedupe:
                if to_addr in addresses_seen:
                    # We've already seen this address, so move on.
                    continue
                addresses_seen.add(to_addr)

            if interrupted_progress and contact_key <= interrupted_progress:
                # We are still working through the backlog of a previously
                # interrupted bulk send command, so don't actually send the
                # message. This check is safe because our contact keys are both
                # sorted and unique.
                continue

            # We can now send the message and update the progress tracker.
            yield self.send_message_via_window(
                conv, window_id, batch_id, to_addr, msg_options, content)
            yield self.set_send_progress(conv, cmd_id, contact_key)

        # All finished, so clear the send progress.
        yield self.clear_send_progress(conv, cmd_id)

    def consume_ack(self, event):
        return self.handle_event(event)

    def consume_nack(self, event):
        return self.handle_event(event)

    @inlineCallbacks
    def handle_event(self, event):
        message = yield self.find_message_for_event(event)
        if message is None:
            log.error('Unable to find message for %s, user_message_id: %s' % (
                event['event_type'], event.get('user_message_id')))
            return

        msg_mdh = self.get_metadata_helper(message)
        conv = yield msg_mdh.get_conversation()
        if conv:
            window_id = self.get_window_id(conv.key, conv.batch.key)
            flight_key = yield self.window_manager.get_internal_id(
                window_id, message['message_id'])
            yield self.window_manager.remove_key(window_id, flight_key)
