# -*- test-case-name: go.apps.bulk_message.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""
from twisted.internet.defer import inlineCallbacks

from vumi.middleware.tagger import TaggingMiddleware
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker
from go.vumitools.window_manager import WindowManager


class BulkMessageApplication(GoApplicationWorker):
    """
    Application that accepts 'send message' commands and does exactly that.
    """
    SEND_TO_TAGS = frozenset(['default'])
    worker_name = 'bulk_message_application'
    max_ack_window = 100
    max_ack_wait = 10
    max_ack_retries = 10
    monitor_interval = 10
    monitor_window_cleanup = True

    @inlineCallbacks
    def setup_application(self):
        yield super(BulkMessageApplication, self).setup_application()
        self.window_manager = WindowManager(self.redis,
            window_size=self.max_ack_window,
            flight_lifetime=self.max_ack_wait,
            max_flight_retries=self.max_ack_retries)
        self.window_manager.monitor(self.on_window_key_ready,
            interval=self.monitor_interval,
            cleanup=self.monitor_window_cleanup,
            cleanup_callback=self.on_window_cleanup)

    def teardown_application(self):
        self.window_manager.stop()

    @inlineCallbacks
    def on_window_key_ready(self, window_id, flight_key):
        data = yield self.window_manager.get_data(window_id, flight_key)
        batch_id = data['batch_id']
        to_addr = data['to_addr']
        content = data['content']
        msg_options = data['msg_options']
        msg = yield self.send_to(to_addr, content, **msg_options)
        yield self.vumi_api.mdb.add_outbound_message(msg, batch_id=batch_id)
        self.window_manager.set_external_id(window_id, flight_key,
            msg['message_id'])
        log.info('Stored outbound %s' % (msg,))

    def on_window_cleanup(self, window_id):
        log.info('Finished window %s, removing.' % (window_id,))

    def get_window_id(self, conversation_key, batch_id):
        return ':'.join([conversation_key, batch_id])

    @inlineCallbacks
    def send_message(self, window_id, batch_id, to_addr, content, msg_options):
        yield self.window_manager.create_window(window_id, strict=False)
        yield self.window_manager.add(window_id, {
            'batch_id': batch_id,
            'to_addr': to_addr,
            'content': content,
            'msg_options': msg_options,
            })

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):

        if is_client_initiated:
            log.warning('Trying to start a client initiated conversation '
                'on a bulk message send.')
            return

        conv = yield self.get_conversation(batch_id, conversation_key)
        if conv is None:
            log.warning('Cannot find conversation for batch_id: %s '
                'and conversation_key: %s' % (batch_id, conversation_key))
            return

        to_addresses = yield conv.get_opted_in_addresses()
        if extra_params.get('dedupe'):
            to_addresses = set(to_addresses)

        window_id = self.get_window_id(conversation_key, batch_id)
        for to_addr in to_addresses:
            yield self.send_message(window_id, batch_id, to_addr,
                                    conv.message, msg_options)

    def consume_user_message(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        return self.vumi_api.mdb.add_inbound_message(msg, tag=tag)

    @inlineCallbacks
    def consume_ack(self, event):
        yield self.vumi_api.mdb.add_event(event)

        message = yield self.find_message_for_event(event)
        if message is None:
            log.error('Unable to find message for %s, user_message_id: %s' % (
                event['event_type'], event.get('user_message_id')))
            return

        gm = self.get_go_metadata(message)
        conversation = yield gm.get_conversation()
        batch_key = yield gm.get_batch_key()
        if conversation and batch_key:
            window_id = self.get_window_id(conversation.key, batch_key)
            flight_key = self.window_manager.get_internal_id(window_id,
                message['message_id'])
            yield self.window_manager.remove_key(window_id, flight_key)

    def consume_delivery_report(self, event):
        return self.vumi_api.mdb.add_event(event)

    def close_session(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        return self.vumi_api.mdb.add_inbound_message(msg, tag=tag)
