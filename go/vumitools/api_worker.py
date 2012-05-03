# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application import ApplicationWorker
from vumi.persist.message_store import MessageStore
from vumi.persist.txriak_manager import TxRiakManager
from vumi.dispatchers.base import BaseDispatchRouter
from vumi.middleware.tagger import TaggingMiddleware
from vumi import log

from go.vumitools.api import VumiApiCommand, get_redis
from go.vumitools.account import AccountStore
from go.vumitools.conversation import ConversationStore


class CommandDispatcher(ApplicationWorker):
    """
    An application worker that forwards commands arriving on the Vumi Api
    queue to the relevant applications. It does this by using the commands
    worker_name parameter to construct the routing key.

    Configuration parameters:

    :type api_routing: dict
    :param api_routing:
        Dictionary describing where to consume API commands.
    :type worker_names: list
    :param worker_names:
        A list of known worker names that we can forward
        VumiApiCommands to.
    """

    def validate_config(self):
        self.api_routing_config = VumiApiCommand.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        self.api_consumer = None
        self.worker_names = self.config.get('worker_names', [])

    @inlineCallbacks
    def setup_application(self):
        self.worker_publishers = {}
        for worker_name in self.worker_names:
            worker_publisher = yield self.publish_to('%s.control' % (
                worker_name,))
            self.worker_publishers[worker_name] = worker_publisher

        self.api_consumer = yield self.consume(
            self.api_routing_config['routing_key'],
            self.consume_control_command,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiCommand)

    @inlineCallbacks
    def teardown_application(self):
        if self.api_consumer:
            yield self.api_consumer.stop()
            self.api_consumer = None

    @inlineCallbacks
    def consume_control_command(self, cmd):
        worker_name = cmd.get('worker_name')
        publisher = self.worker_publishers.get(worker_name)
        if publisher:
            yield publisher.publish_message(cmd)
            log.info('Sent %s to %s' % (cmd, worker_name))
        else:
            log.error('No worker publisher available for %s' % (cmd,))


class GoApplicationRouter(BaseDispatchRouter):
    """
    Router for a dispatcher that routes messages
    based on their tags.

    """
    def setup_routing(self):
        # map conversation types to applications that deal with them
        self.conversation_mappings = self.config['conversation_mappings']
        # setup the message_store
        mdb_config = self.config.get('message_store', {})
        self.mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        r_server = get_redis(self.config)
        self.manager = TxRiakManager.from_config({
                'bucket_prefix': self.mdb_prefix})
        self.account_store = AccountStore(self.manager)
        self.message_store = MessageStore(self.manager, r_server,
                                            self.mdb_prefix)

    @inlineCallbacks
    def get_conversation_for_tag(self, tag):
        current_tag = yield self.message_store.get_tag_info(tag)
        if current_tag:
            batch = yield current_tag.current_batch.get()
            account_key = batch.metadata.user_account
            if account_key:
                conversation_store = ConversationStore(self.manager,
                    account_key)
                account_submanager = conversation_store.manager
                all_conversations = yield batch.backlinks.conversations(
                                                        account_submanager)
                conversations = [c for c in all_conversations if not
                                    c.ended()]
                if conversations:
                    if len(conversations) > 1:
                        conv_keys = [c.key for c in conversations]
                        log.warning('Multiple conversations found '
                            'going with most recent: %r' % (conv_keys,))
                    conversation = sorted(conversations, reverse=True,
                        key=lambda c: c.start_timestamp)[0]
                    returnValue(conversation)
                log.error('No conversations found for %r' % (batch,))
            else:
                log.error('No account_key found for tag: %r, batch: %r' % (
                    current_tag, batch))
        else:
            log.error('Cannot find current tag for %s' % (tag,))

    @inlineCallbacks
    def find_application_for_msg(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        if tag:
            conversation = yield self.get_conversation_for_tag(tag)
            if conversation:
                conv_type = conversation.conversation_type
                metadata = msg['helper_metadata']
                conv_metadata = metadata.setdefault('conversations', {})
                conv_metadata.update({
                    'conversation_key': conversation.key,
                    'conversation_type': conv_type,
                })
                returnValue(self.conversation_mappings.get(conv_type))

    @inlineCallbacks
    def dispatch_inbound_message(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        self.message_store.add_inbound_message(msg, tag=tag)
        application = yield self.find_application_for_msg(msg)
        if application:
            publisher = self.dispatcher.exposed_publisher[application]
            yield publisher.publish_message(msg)
        else:
            log.error('No application setup for type: %s' % (
                        msg,))

    def dispatch_inbound_event(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        self.message_store.add_event(msg, tag=tag)
        application = self.find_application_for_msg(msg)
        if application:
            publisher = self.dispatcher.exposed_event_publisher[application]
            yield publisher.publish_message(msg)
        else:
            log.error('No application setup for type: %s' % (
                        msg,))

    def dispatch_outbound_message(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        self.message_store.add_outbound_message(msg, tag=tag)
        upstream = self.dispatcher.transport_publisher.keys()[0]
        self.dispatcher.transport_publisher[upstream].publish_message(msg)
