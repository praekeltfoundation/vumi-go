# -*- test-case-name: go.apps.bulk_message.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.middleware import TaggingMiddleware
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker

# from twisted.internet.defer import inlineCallbacks

# from vumi.application import ApplicationWorker
# from vumi.components.message_store import MessageStore
# from vumi.persist.txriak_manager import TxRiakManager
# from vumi.persist.txredis_manager import TxRedisManager
# from vumi.middleware import TaggingMiddleware
# from vumi import log

# from go.vumitools.api import VumiApiCommand
# from go.vumitools.conversation import ConversationStore
# from go.vumitools.middleware import DebitAccountMiddleware


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

        to_addresses = yield conv.get_opted_in_addresses()
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
