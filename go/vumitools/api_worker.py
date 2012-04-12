# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.application import ApplicationWorker, MessageStore
from vumi.message import TransportUserMessage
from vumi import log

from go.vumitools.api import VumiApiCommand, get_redis


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
        content = cmd['content']
        msg_options = cmd['msg_options']
        to_addr = cmd['to_addr']
        yield self.send_to(to_addr, content, **msg_options)

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
            transport_lookup_map[transport_type]: from_addr
        })
        if contacts.exists():
            contact = contacts.latest()
            groups = contact.groups.all()
            conversations = Conversation.objects.filter(end_time__isnull=True,
                    groups__in=groups).order_by('-created_at')
            if conversations.exists():
                conversation = conversations.latest()
                print 'this needs to go conversation', conversation
                publisher = self.application_publishers.get(
                                conversation.conversation_type)
                if publisher:
                    metadata = msg['helper_metadata']
                    metadata['poll_id'] = 'poll-%s' % (conversation.pk,)
                    metadata['conversation_id'] = conversation.pk
                    publisher.publish_message(msg)
