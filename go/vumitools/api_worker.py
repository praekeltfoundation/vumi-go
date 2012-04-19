# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.application import ApplicationWorker, MessageStore
from vumi.dispatchers.base import BaseDispatchRouter
from vumi.middleware.tagger import TaggingMiddleware
from vumi.message import TransportUserMessage
from vumi import log

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
        worker_name = cmd.get('worker_name')
        publisher = self.worker_publishers.get(worker_name)
        if publisher:
            yield publisher.publish_message(cmd)
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
        self.store = MessageStore(r_server, self.mdb_prefix)

    def get_conversation_type_for_tag(self, tag):
        from go.conversation.models import MessageBatch
        batch_id = self.store.tag_common(tag)['current_batch_id']
        try:
            batch = MessageBatch.objects.get(batch_id=batch_id)
            conversation = batch.preview_batch or batch.message_batch
            if conversation:
                return {
                    'conversation_id': conversation.pk,
                    'conversation_type': conversation.conversation_type,
                }
            else:
                log.error('Cannot find conversation for %s' % (batch_id,))
        except MessageBatch.DoesNotExist:
            log.error('Cannot find batch for %s' % (batch_id,))
        return {}

    def find_application_for_msg(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        conv_info = self.get_conversation_for_tag(tag)
        conv_metadata = msg['helper_metadata'].setdefault('conversations', {})
        conv_metadata.update(conv_info)
        conv_type = conv_metadata.get('conversation_type')
        return self.conversation_mappings.get(conv_type)

    @inlineCallbacks
    def dispatch_inbound_message(self, msg):
        application = self.find_application_for_msg(msg)
        if application:
            publisher = self.dispatcher.exposed_publisher[application]
            yield publisher.publish_message(msg)
        else:
            log.error('No application setup for type: %s' % (
                        msg,))

    def dispatch_inbound_event(self, msg):
        application = self.find_application_for_msg(msg)
        if application:
            publisher = self.dispatcher.exposed_event_publisher[application]
            yield publisher.publish_message(msg)
        else:
            log.error('No application setup for type: %s' % (
                        msg,))

    def dispatch_outbound_message(self, msg):
        name = msg['transport_name']
        name = self.config.get('transport_mappings', {}).get(name, name)
        self.dispatcher.transport_publisher[name].publish_message(msg)


class VumiApiWorker(ApplicationWorker):
    """An application worker that provides a RabbitMQ and message-store
    based API for outside applications to interact with.

    Configuration parameters:

    :type api_routing: dict
    :param api_routing:
        Dictionary describing where to consume API commands.
    """

    SEND_TO_TAGS = frozenset(['default'])

    def validate_config(self):
        # message store
        mdb_config = self.config.get('message_store', {})
        self.mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        # api worker
        self.api_routing_config = VumiApiCommand.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        print 'api_routing', self.api_routing_config
        self.api_consumer = None
        self.applications = self.config.get('applications', {})

    @inlineCallbacks
    def setup_application(self):
        r_server = get_redis(self.config)
        self.store = MessageStore(r_server, self.mdb_prefix)
        self.api_consumer = yield self.consume(
            self.api_routing_config['routing_key'],
            self.consume_api_command,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiCommand)


        self.application_publishers = {}
        for app_type, app_transport_name in self.applications.items():
            # Consume the outbound messages so we can funnel
            # them back out again to the relevant transport.
            app_consumer = yield self.consume('%s.outbound' % (
                app_transport_name,), self.handle_application_message,
                message_class=TransportUserMessage)
            self._consumers.append(app_consumer)

            # Publish messages meant for the app to the appropriate
            # routing key & queue
            app_publisher = yield self.publish_to('%s.inbound' % (
                app_transport_name,))

            self.application_publishers[app_type] = app_publisher


    @inlineCallbacks
    def teardown_application(self):
        if self.api_consumer is not None:
            yield self.api_consumer.stop()
            self.api_consumer = None

    def process_unknown_cmd(self, cmd):
        log.error("Unknown vumi API command: %r" % (cmd,))

    @inlineCallbacks
    def process_cmd_send(self, cmd):
        batch_id = cmd['batch_id']
        content = cmd['content']
        msg_options = cmd['msg_options']
        to_addr = cmd['to_addr']
        print 'sending to', to_addr, content, msg_options
        msg = yield self.send_to(to_addr, content, **msg_options)
        self.store.add_outbound_message(msg, batch_id=batch_id)
        print 'stored outbound', msg

    def consume_api_command(self, cmd):
        cmd_method_name = 'process_cmd_%s' % (cmd.get('command'),)
        cmd_method = getattr(self, cmd_method_name,
                             self.process_unknown_cmd)
        return cmd_method(cmd)

    @inlineCallbacks
    def handle_application_message(self, msg):
        yield self.transport_publisher.publish_message(msg)

    def consume_user_message(self, msg):
        from go.conversation.models import Conversation
        from go.contacts.models import Contact

        from_addr = msg['from_addr'].split('/', 1)[0]
        transport_type = msg['transport_type']

        transport_lookup_map = {
            'xmpp': 'gtalk_id',
            'sms': 'msisdn'
        }

        contacts = Contact.objects.filter(**{
            '%s__endswith' % (transport_lookup_map[transport_type],): from_addr
        })

        if contacts.exists():
            contact = contacts.latest()
            groups = contact.groups.all()
            print 'contact', contact
            print 'groups', groups
            conversations = Conversation.objects.filter(end_time__isnull=True,
                    delivery_class=msg['helper_metadata']['tag']['tag'][0],
                    groups__in=groups).order_by('-created_at')
            print 'conversations', conversations
            if conversations.exists():
                conversation = conversations.latest()
                print 'this needs to go conversation', conversation
                if conversation.preview_batch_set.exists():
                    batch = conversation.preview_batch_set.latest('pk')
                elif conversation.message_batch_set.exists():
                    batch = conversation.message_batch_set.latest('pk')
                else:
                    batch = None

                print 'storing in batch', batch.batch_id
                if batch:
                    self.store.add_inbound_message(msg,
                                                    batch_id=batch.batch_id)
                    publisher = self.application_publishers.get(
                                    conversation.conversation_type)
                    if publisher:
                        metadata = msg['helper_metadata']
                        metadata['poll_id'] = 'poll-%s' % (conversation.pk,)
                        metadata['conversation_id'] = conversation.pk
                        publisher.publish_message(msg)
