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
from vumi.errors import VumiError

from go.vumitools.api import VumiApiCommand, get_redis


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
        self.api_consumer = yield self.consume(
            self.api_routing_config['routing_key'],
            self.consume_api_command,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiCommand)

        self.worker_publishers = {}
        for worker_name in self.worker_names:
            worker_publisher = yield self.publish_to('%s.control' % (
                worker_name,))
            self.worker_publishers[worker_name] = worker_publisher

    @inlineCallbacks
    def teardown_application(self):
        if self.api_consumer:
            yield self.api_consumer.stop()
            self.api_consumer = None

    @inlineCallbacks
    def consume_api_command(self, cmd):
        msg_options = cmd.get('msg_options', {})
        worker_name = msg_options.get('worker_name')
        publisher = self.worker_publishers.get(worker_name)
        if publisher:
            yield publisher.publish_message(cmd)
            log.info('Sent %s to %s' % (cmd, worker_name))
        else:
            log.error('No worker publisher available for %s' % (worker_name,))


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
        self.store = MessageStore(self.manager, r_server, self.mdb_prefix)

    @inlineCallbacks
    def get_conversation_for_tag(self, tag):
        tag_info = yield self.store.get_tag_info(tag)
        if tag_info:
            batch_id = tag_info.current_batch.key
            print 'batch_id', batch_id
            returnValue({'something': 'relevant'})
        else:
            log.error('Cannot find tag info for %s' % (tag,))
        returnValue({})
        # raise Exception('eeeeep')
        # returnValue({})
        # print 'tag_info', tag_info
        # batch_id = tag_info.current_batch.key
        # print 'batch_id', batch_id
        # raise Exception('eeeop')
        # print 'excception raised and ignored?'
        # try:
        #     batch = MessageBatch.objects.get(batch_id=batch_id)
        #     conversation = batch.preview_batch or batch.message_batch
        #     if conversation:
        #         returnValue({
        #             'conversation_id': conversation.pk,
        #             'conversation_type': conversation.conversation_type,
        #         })
        #     else:
        #         log.error('Cannot find conversation for %s' % (batch_id,))
        # except MessageBatch.DoesNotExist:
        #     log.error('Cannot find batch for %s' % (batch_id,))
        # returnValue({})

    @inlineCallbacks
    def find_application_for_msg(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        if tag:
            conv_info = yield self.get_conversation_for_tag(tag)
            metadata = msg['helper_metadata']
            conv_metadata = metadata.setdefault('conversations', {})
            conv_metadata.update(conv_info)
            conv_type = conv_metadata.get('conversation_type')
            returnValue(self.conversation_mappings.get(conv_type))

    @inlineCallbacks
    def dispatch_inbound_message(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        self.store.add_inbound_message(msg, tag=tag)
        application = yield self.find_application_for_msg(msg)
        if application:
            publisher = self.dispatcher.exposed_publisher[application]
            yield publisher.publish_message(msg)
        else:
            log.error('No application setup for type: %s' % (
                        msg,))

    def dispatch_inbound_event(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        self.store.add_event(msg, tag=tag)
        application = self.find_application_for_msg(msg)
        if application:
            publisher = self.dispatcher.exposed_event_publisher[application]
            yield publisher.publish_message(msg)
        else:
            log.error('No application setup for type: %s' % (
                        msg,))

    def dispatch_outbound_message(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        self.store.add_outbound_message(msg, tag=tag)
        upstream = self.dispatcher.transport_publisher.keys()[0]
        self.dispatcher.transport_publisher[upstream].publish_message(msg)
