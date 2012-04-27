# -*- test-case-name: go.vumitools.tests.test_bulk_send_application -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.application import ApplicationWorker, MessageStore
from vumi.middleware import TaggingMiddleware
from vumi import log

from go.vumitools.api import VumiApiCommand, get_redis


class GoApplication(ApplicationWorker):
    """
    A base class for Vumi Go application worker.

    Configuration parameters:

    :type worker_name: str
    :param worker_name:
        The name of this worker, used for receiving control messages.

    """

    worker_name = None

    def validate_config(self):
        self.worker_name = self.config.get('worker_name', self.worker_name)
        # message store
        mdb_config = self.config.get('message_store', {})
        self.mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        # api worker
        self.api_routing_config = VumiApiCommand.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        self.control_consumer = None

    @inlineCallbacks
    def setup_application(self):
        r_server = get_redis(self.config)
        self.store = MessageStore(r_server, self.mdb_prefix)
        self.control_consumer = yield self.consume(
            '%s.control' % (self.worker_name,),
            self.consume_control_command,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiCommand)

    @inlineCallbacks
    def teardown_application(self):
        if self.control_consumer is not None:
            yield self.control_consumer.stop()
            self.control_consumer = None

    def consume_control_command(self, command_message):
        """
        Handle a VumiApiCommand message that has arrived.

        :type command_message: VumiApiCommand
        :param command_message:
            The command message received for this application.
        """
        cmd_method_name = 'process_command_%(command)s' % command_message
        args = command_message['args']
        kwargs = command_message['kwargs']
        cmd_method = getattr(self, cmd_method_name, None)
        if cmd_method:
            return cmd_method(*args, **kwargs)
        else:
            return self.process_unknown_cmd(cmd_method_name, )

    def process_unknown_cmd(self, method_name, *args, **kwargs):
        log.error("Unknown vumi API command: %s(%s, %s)" % (
            method_name, args, kwargs))

    def consume_user_message(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        self.store.add_inbound_message(msg, tag=tag)

    def consume_ack(self, event):
        self.store.add_event(event)

    def consume_delivery_report(self, event):
        self.store.add_event(event)

    def close_session(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        self.store.add_inbound_message(msg, tag=tag)


class BulkSendApplication(GoApplication):
    """
    Application that accepts 'send message' commands and does exactly that.
    """
    SEND_TO_TAGS = frozenset(['default'])
    worker_name = 'bulk_send_application'

    @inlineCallbacks
    def process_command_start(self, batch_id, content, to_addresses,
                                msg_options):
        for to_addr in to_addresses:
            msg = yield self.send_to(to_addr, content, **msg_options)
            self.store.add_outbound_message(msg, batch_id=batch_id)
            log.info('Stored outbound %s' % (msg,))
