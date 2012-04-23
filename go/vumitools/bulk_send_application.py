# -*- test-case-name: go.vumitools.tests.test_bulk_send_application -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.application import ApplicationWorker, MessageStore
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
        cmd_method_name = 'process_command_%s' % (
            command_message.get('command'),)
        cmd_method = getattr(self, cmd_method_name,
                             self.process_unknown_cmd)
        return cmd_method(command_message)

    def process_unknown_cmd(self, command_message):
        log.error("Unknown vumi API command: %r" % (command_message,))

    def consume_user_message(self, msg):
        log.info('Received Message: %s' % (msg,))

    def consume_ack(self, event):
        log.info('Received Ack: %s' % (event,))

    def consume_delivery_report(self, event):
        log.info('Received Delivery Report: %s' % (event,))

    def close_session(self, msg):
        log.info('Received Close Session: %s' % (msg,))



class BulkSendApplication(GoApplication):
    """
    Application that accepts 'send message' commands and does exactly that.
    """
    SEND_TO_TAGS = frozenset(['default'])
    worker_name = 'bulk_send_application'

    @inlineCallbacks
    def process_command_send(self, cmd):
        batch_id = cmd['batch_id']
        content = cmd['content']
        msg_options = cmd['msg_options']
        to_addr = cmd['to_addr']
        log.info('Sending to %s %s %s'% (to_addr, content, msg_options,))
        msg = yield self.send_to(to_addr, content, **msg_options)
        self.store.add_outbound_message(msg, batch_id=batch_id)
        log.info('Stored outbound %s'% (msg,))
