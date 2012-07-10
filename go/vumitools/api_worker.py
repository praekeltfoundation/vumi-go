# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application import ApplicationWorker
from vumi.dispatchers.base import BaseDispatchRouter
from vumi.utils import load_class_by_string
from vumi import log
from vumi.persist.txriak_manager import TxRiakManager

from go.vumitools.account import AccountStore
from go.vumitools.api import VumiApiCommand, VumiApiEvent
from go.vumitools.middleware import (LookupConversationMiddleware,
    OptOutMiddleware)


class CommandDispatcher(ApplicationWorker):
    """
    An application worker that forwards commands arriving on the Vumi Api queue
    to the relevant applications. It does this by using the command's
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


class EventDispatcher(ApplicationWorker):
    """
    An application worker that forwards event arriving on the Vumi Api Event
    queue to the relevant handlers.

    FIXME: The configuration is currently static.

    Configuration parameters:

    :type api_routing: dict
    :param api_routing:
        Dictionary describing where to consume API commands.
    :type handler_names: list
    :param event_handlers:
        A mapping from handler name to fully-qualified class name.
    """

    def validate_config(self):
        self.api_routing_config = VumiApiEvent.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        self.api_consumer = None
        self.handler_config = self.config.get('event_handlers', {})
        self.account_handler_configs = self.config.get('account_handler_configs', {})
        mdb_config = self.config.get('message_store', {})
        self.mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        self.r_prefix = self.config.get('r_prefix')

    @inlineCallbacks
    def setup_application(self):
        self.handlers = {}
        setup_deferreds = []
        for name, handler_class in self.handler_config.items():
            cls = load_class_by_string(handler_class)
            self.handlers[name] = cls(self, self.config.get(name, {}))
            yield setup_deferreds.append(self.handlers[name].setup_handler())

        self.api_command_publisher = yield self.publish_to('vumi.api')
        self.manager = TxRiakManager.from_config(
            {'bucket_prefix': self.mdb_prefix})
        self.account_store = AccountStore(self.manager)
        self.account_config = {}

        self.api_event_consumer = yield self.consume(
            self.api_routing_config['routing_key'],
            self.consume_api_event,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiEvent)

    @inlineCallbacks
    def teardown_application(self):
        if self.api_event_consumer:
            yield self.api_event_consumer.stop()
            self.api_event_consumer = None

    @inlineCallbacks
    def get_account_config(self, account_key):
        if account_key not in self.account_config:
            user_account = yield self.account_store.get_user(account_key)
            event_handler_config = {}
            for k, v in (user_account.event_handler_config or \
                    self.account_handler_configs.get(account_key) or []):
                event_handler_config[tuple(k)] = v
            self.account_config[account_key] = event_handler_config
        returnValue(self.account_config[account_key])

    @inlineCallbacks
    def consume_api_event(self, event):
        log.msg("Handling event: %r" % (event,))
        config = yield self.get_account_config(event['account_key'])
        for handler, handler_config in config.get(
            (event['conversation_key'], event['event_type']), []):
            yield self.handlers[handler].handle_event(event, handler_config)


class GoApplicationRouter(BaseDispatchRouter):
    """
    Router for a dispatcher that routes messages
    based on their tags.

    """
    def setup_routing(self):
        # map conversation types to applications that deal with them
        self.conversation_mappings = self.config['conversation_mappings']
        self.upstream_transport = self.config['upstream_transport']
        self.optout_transport = self.config['optout_transport']

    def find_application_for_msg(self, msg):
        # Sometimes I don't like pep8
        helper = LookupConversationMiddleware.map_message_to_conversation_info
        conversation_info = helper(msg)
        if conversation_info:
            conversation_key, conversation_type = conversation_info
            return self.conversation_mappings[conversation_type]

    @inlineCallbacks
    def dispatch_inbound_message(self, msg):
        application = self.find_application_for_msg(msg)
        if OptOutMiddleware.is_optout_message(msg):
            publisher = self.dispatcher.exposed_publisher[
                self.optout_transport]
            yield publisher.publish_message(msg)
        else:
            if application:
                publisher = self.dispatcher.exposed_publisher[application]
                yield publisher.publish_message(msg)
            else:
                log.error('No application setup for inbound message '
                            'type: %s' % (msg,))

    @inlineCallbacks
    def dispatch_inbound_event(self, msg):
        application = self.find_application_for_msg(msg)
        if application:
            publisher = self.dispatcher.exposed_event_publisher[application]
            yield publisher.publish_message(msg)
        else:
            log.error('No application setup for inbount event type: %s' % (
                        msg,))

    @inlineCallbacks
    def dispatch_outbound_message(self, msg):
        pub = self.dispatcher.transport_publisher[self.upstream_transport]
        yield pub.publish_message(msg)
