# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.application import ApplicationWorker
from vumi import log

from go.vumitools.api import VumiApiCommand, MessageStore, get_redis


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

    def consume_user_message(self, msg):
        self.store.add_inbound_message(msg)

    def close_session(self, msg):
        self.store.add_inbound_message(msg)
