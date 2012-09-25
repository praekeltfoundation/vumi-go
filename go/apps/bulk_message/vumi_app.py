# -*- test-case-name: go.apps.bulk_message.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.middleware.tagger import TaggingMiddleware
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker


class BulkMessageApplication(GoApplicationWorker):
    """
    Application that accepts 'send message' commands and does exactly that.
    """
    SEND_TO_TAGS = frozenset(['default'])
    worker_name = 'bulk_message_application'

    @inlineCallbacks
    def send_message(self, batch_id, to_addr, content, msg_options):
        msg = yield self.send_to(to_addr, content, **msg_options)
        yield self.vumi_api.mdb.add_outbound_message(msg, batch_id=batch_id)
        log.info('Stored outbound %s' % (msg,))

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
        for to_addr in to_addresses:
            yield self.send_message(batch_id, to_addr,
                                    conv.message, msg_options)

    def consume_user_message(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        return self.vumi_api.mdb.add_inbound_message(msg, tag=tag)

    def consume_ack(self, event):
        return self.vumi_api.mdb.add_event(event)

    def consume_delivery_report(self, event):
        return self.vumi_api.mdb.add_event(event)

    def close_session(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        return self.vumi_api.mdb.add_inbound_message(msg, tag=tag)

    @inlineCallbacks
    def process_command_send_message(self, *args, **kwargs):
        command_data = kwargs['command_data']
        log.info('Processing send_message: %s' % kwargs)
        yield self.send_message(
                command_data['batch_id'],
                command_data['to_addr'],
                command_data['content'],
                command_data['msg_options'])
