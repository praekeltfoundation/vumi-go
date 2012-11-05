# -*- test-case-name: go.apps.bulk_message.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""
from twisted.internet.defer import inlineCallbacks, returnValue

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
    monitor_interval = 1
    monitor_window_cleanup = True

    @inlineCallbacks
    def setup_application(self):
        yield super(BulkMessageApplication, self).setup_application()
        wm_redis = self.redis.sub_manager('%s:window_manager' % (
            self.worker_name,))
        self.window_manager = WindowManager(wm_redis,
            window_size=self.max_ack_window,
            flight_lifetime=self.max_ack_wait)
        self.window_manager.monitor(self.on_window_key_ready,
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
        batch_id = data['batch_id']
        to_addr = data['to_addr']
        content = data['content']
        msg_options = data['msg_options']
        msg = yield self.send_message(batch_id, to_addr, content, msg_options)
        yield self.window_manager.set_external_id(window_id, flight_key,
            msg['message_id'])

    def on_window_cleanup(self, window_id):
        log.info('Finished window %s, removing.' % (window_id,))

    def get_window_id(self, conversation_key, batch_id):
        return ':'.join([conversation_key, batch_id])

    @inlineCallbacks
    def send_message_via_window(self, window_id, batch_id, to_addr, content,
                                    msg_options):
        yield self.window_manager.create_window(window_id, strict=False)
        yield self.window_manager.add(window_id, {
            'batch_id': batch_id,
            'to_addr': to_addr,
            'content': content,
            'msg_options': msg_options,
            })

    @inlineCallbacks
    def send_message(self, batch_id, to_addr, content, msg_options):
        msg = yield self.send_to(to_addr, content, **msg_options)
        returnValue(msg)

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
            yield self.send_message_via_window(window_id, batch_id, to_addr,
                                    conv.message, msg_options)

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

        gm = self.get_go_metadata(message)
        conversation = yield gm.get_conversation()
        batch_key = yield gm.get_batch_key()
        if conversation and batch_key:
            window_id = self.get_window_id(conversation.key, batch_key)
            flight_key = yield self.window_manager.get_internal_id(window_id,
                                message['message_id'])
            yield self.window_manager.remove_key(window_id, flight_key)

    @inlineCallbacks
    def process_command_send_message(self, *args, **kwargs):
        command_data = kwargs['command_data']
        log.info('Processing send_message: %s' % kwargs)
        yield self.send_message(
                command_data['batch_id'],
                command_data['to_addr'],
                command_data['content'],
                command_data['msg_options'])

    @inlineCallbacks
    def collect_metrics(self, user_api, conversation_key):
        conv = yield user_api.get_wrapped_conversation(conversation_key)
        yield self.collect_message_metrics(conv)
