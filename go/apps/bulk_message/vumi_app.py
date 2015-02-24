# -*- test-case-name: go.apps.bulk_message.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""
from twisted.internet.defer import inlineCallbacks

from vumi.components.window_manager import WindowManager
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker


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
        msg = yield self.send_to(
            to_addr, content, endpoint='default', **msg_options)
        yield self.window_manager.set_external_id(
            window_id, flight_key, msg['message_id'])

    def on_window_cleanup(self, window_id):
        log.info('Finished window %s, removing.' % (window_id,))

    def get_window_id(self, conversation_key, batch_id):
        return ':'.join([conversation_key, batch_id])

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
    def process_command_bulk_send(self, user_account_key, conversation_key,
                                  batch_id, msg_options, content, dedupe,
                                  delivery_class, **extra_params):

        conv = yield self.get_conversation(user_account_key, conversation_key)
        if conv is None:
            log.warning("Cannot find conversation '%s' for user '%s'." % (
                conversation_key, user_account_key))
            return

        to_addresses = []
        for contacts_batch in (
                yield conv.get_opted_in_contact_bunches(delivery_class)):
            for contact in (yield contacts_batch):
                to_addresses.append(contact.addr_for(delivery_class))
        if dedupe:
            to_addresses = set(to_addresses)

        self.add_conv_to_msg_options(conv, msg_options)
        window_id = self.get_window_id(conversation_key, batch_id)
        for to_addr in to_addresses:
            yield self.send_message_via_window(
                conv, window_id, batch_id, to_addr, msg_options, content)

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
