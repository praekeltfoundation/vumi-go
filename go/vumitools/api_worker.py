# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.application import ApplicationWorker
from vumi import log

from go.vumitools.api import VumiApiCommand


class VumiApiWorker(ApplicationWorker):
    """An application worker that provides a RabbitMQ and message-store
    based API for outside applications to interact with.

    Configuration parameters:

    :type api_routing: dict
    :param api_routing:
        Dictionary describing where to consume API commands.
    """

    # TODO: Vumi application worker will need to grow
    #       support for sending messages that are not
    #       replies

    def validate_config(self):
        self.api_routing_config = VumiApiCommand.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        self.api_consumer = None

    @inlineCallbacks
    def setup_application(self):
        self.api_consumer = yield self.consume(
            self.api_routing_config['routing_key'],
            self.consume_api_command,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiCommand)

    def teardown_application(self):
        if self.api_consumer is not None:
            yield self.api_consumer.stop()
            self.api_consumer = None

    def process_unknown_cmd(self, cmd):
        log.error("Unknown vumi API command: %r" % (cmd,))

    def process_cmd_send(self, cmd):
        batch_id = cmd['batch_id']
        content = cmd['content']
        to_addr = cmd['to_addr']
        # TODO add message to batch_id
        self.send_to(to_addr, content)

    def consume_api_command(self, cmd):
        cmd_method_name = 'process_cmd_%s' % (cmd.get('command'),)
        cmd_method = getattr(self, cmd_method_name,
                             self.process_unknown_cmd)
        return cmd_method(cmd)

    def consume_ack(self, event):
        pass

    def consume_delivery_report(self, event):
        pass

    def consume_user_message(self, msg):
        pass

    def close_session(self, msg):
        pass
