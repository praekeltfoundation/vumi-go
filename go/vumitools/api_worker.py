# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.application import ApplicationWorker, MessageStore
from vumi import log

from go.vumitools.api import VumiApiCommand, get_redis

from django.conf import settings


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
        vxpolls_transport_name = '%(transport_name)s.inbound' % {
            'transport_name': settings.VXPOLLS_TRANSPORT_NAME,
        }
        print vxpolls_transport_name
        self.vxpolls_publisher = yield self.publish_to(vxpolls_transport_name)

    @inlineCallbacks
    def teardown_application(self):
        if self.api_consumer is not None:
            yield self.api_consumer.stop()
            self.api_consumer = None

    def process_unknown_cmd(self, cmd):
        log.error("Unknown vumi API command: %r" % (cmd,))

    def process_cmd_send(self, cmd):
        batch_id = cmd['batch_id']
        content = cmd['content']
        msg_options = cmd['msg_options']
        to_addr = cmd['to_addr']
        msg = self.send_to(to_addr, content, **msg_options)
        self.store.add_message(batch_id, msg)

    def consume_api_command(self, cmd):
        cmd_method_name = 'process_cmd_%s' % (cmd.get('command'),)
        cmd_method = getattr(self, cmd_method_name,
                             self.process_unknown_cmd)
        return cmd_method(cmd)

    def consume_ack(self, event):
        self.store.add_event(event)

    def consume_delivery_report(self, event):
        self.store.add_event(event)

    @inlineCallbacks
    def consume_user_message(self, msg):
        from go.conversation.models import Conversation
        from go.contacts.models import Contact

        from_addr = msg['from_addr'].split('/', 1)[0]
        transport_type = msg['transport_type']
        self.store.add_inbound_message(msg)
        if transport_type == 'xmpp':
            contacts = Contact.objects.filter(gtalk_id=from_addr)
        elif transport_type == 'sms':
            contacts = Contact.objects.filter(msisdn=from_addr)
        if contacts.exists():
            contact = contacts[0]
            groups = contact.groups.all()
            conversations = Conversation.objects.filter(end_time__isnull=True,
                    conversation_type='survey',
                    groups__in=groups).order_by('-created_at')
            if conversations.exists():
                conversation = conversations[0]
                print 'this needs to go conversation', conversation
                msg['helper_metadata']['poll_id'] = 'poll-%s' % (conversation.pk,)
                r = yield self.vxpolls_publisher.publish_message(msg)
                print 'published', r

    def close_session(self, msg):
        self.store.add_inbound_message(msg)
