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
        to_addr = data['to_addr']
        content = data['content']
        msg_options = data['msg_options']
        msg = yield self.send_to(
            to_addr, content, endpoint='default', **msg_options)
        yield self.window_manager.set_external_id(window_id, flight_key,
            msg['message_id'])

    def on_window_cleanup(self, window_id):
        log.info('Finished window %s, removing.' % (window_id,))

    def get_window_id(self, conversation_key, batch_id):
        return ':'.join([conversation_key, batch_id])

    @inlineCallbacks
    def send_message_via_window(self, conv, window_id, batch_id, to_addr,
                                msg_options):
        yield self.window_manager.create_window(window_id, strict=False)
        yield self.window_manager.add(window_id, {
            'batch_id': batch_id,
            'to_addr': to_addr,
            'content': conv.description,
            'msg_options': msg_options,
            })

    def process_command_initial_action_hack(self, *args, **kwargs):
        return self.process_command_bulk_send(*args, **kwargs)

    @inlineCallbacks
    def process_command_bulk_send(self, user_account_key, conversation_key,
                                  batch_id, msg_options, is_client_initiated,
                                  **extra_params):

        if is_client_initiated:
            log.warning('Trying to start a client initiated conversation '
                'on a bulk message send.')
            return

        conv = yield self.get_conversation(user_account_key, conversation_key)
        if conv is None:
            log.warning("Cannot find conversation '%s' for user '%s'." % (
                    user_account_key, conversation_key))
            return

        to_addresses = []
        for contacts_batch in (yield conv.get_opted_in_contact_bunches()):
            for contact in (yield contacts_batch):
                to_addresses.append(contact.addr_for(conv.delivery_class))
        if extra_params.get('dedupe'):
            to_addresses = set(to_addresses)

        self.add_conv_to_msg_options(conv, msg_options)
        window_id = self.get_window_id(conversation_key, batch_id)
        for to_addr in to_addresses:
            yield self.send_message_via_window(
                conv, window_id, batch_id, to_addr, msg_options)

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
        # XXX: This is a really horrible idea.
        batch_key = yield conv.get_latest_batch_key()
        if conv and batch_key:
            window_id = self.get_window_id(conv.key, batch_key)
            flight_key = yield self.window_manager.get_internal_id(window_id,
                                message['message_id'])
            yield self.window_manager.remove_key(window_id, flight_key)

    @inlineCallbacks
    def process_command_send_message(self, user_account_key, conversation_key,
                                     **kwargs):
        conv = yield self.get_conversation(user_account_key, conversation_key)
        command_data = kwargs['command_data']
        log.info('Processing send_message: %s' % kwargs)
        to_addr = command_data['to_addr']
        content = command_data['content']
        msg_options = command_data['msg_options']
        in_reply_to = msg_options.pop('in_reply_to', None)
        self.add_conv_to_msg_options(conv, msg_options)
        if in_reply_to:
            msg = yield self.vumi_api.mdb.get_inbound_message(in_reply_to)
            if msg:
                # TODO: This should no longer be necessary.
                # We can't override transport_name in reply_to(), so we set it
                # on the message we're replying to.
                msg['transport_name'] = msg_options['transport_name']
                yield self.reply_to(
                    msg, content,
                    helper_metadata=msg_options['helper_metadata'])
            else:
                log.warning('Unable to reply, message %s does not exist.' % (
                    in_reply_to))
        else:
            yield self.send_to(
                to_addr, content, endpoint='default', **msg_options)

    @inlineCallbacks
    def collect_metrics(self, user_api, conversation_key):
        conv = yield user_api.get_wrapped_conversation(conversation_key)
        yield self.collect_message_metrics(conv)
