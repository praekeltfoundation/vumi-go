# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application import ApplicationWorker
from vumi.dispatchers.base import BaseDispatchRouter
from vumi.utils import load_class_by_string
from vumi import log

from go.vumitools.api import VumiApi, VumiApiCommand, VumiApiEvent
from go.vumitools.utils import GoMessageMetadata
from go.vumitools.middleware import OptOutMiddleware


class CommandDispatcher(ApplicationWorker):
    """
    An application worker that forwards commands arriving on the Vumi Api queue
    to the relevant applications. It does this by using the command's
    worker_name parameter to construct the routing key.

    Configuration parameters:

    :param dict api_routing:
        Dictionary describing where to consume API commands.
    :param list worker_names:
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
    TODO: We need a "flush cache" command for when the per-account config
          updates.
    TODO: We should wrap the command publisher and such to make event handlers
          saner. Or something.

    Configuration parameters:

    :param dict api_routing:
        Dictionary describing where to consume API commands.
    :param dict event_handlers:
        A mapping from handler name to fully-qualified class name.
    """

    def validate_config(self):
        self.api_routing_config = VumiApiEvent.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        self.api_event_consumer = None
        self.handler_config = self.config.get('event_handlers', {})
        self.account_handler_configs = self.config.get(
            'account_handler_configs', {})

    @inlineCallbacks
    def setup_application(self):
        self.handlers = {}

        self.api_command_publisher = yield self.publish_to('vumi.api')
        self.vumi_api = yield VumiApi.from_config_async(
            self.config, self._amqp_client)
        self.account_config = {}

        for name, handler_class in self.handler_config.items():
            cls = load_class_by_string(handler_class)
            self.handlers[name] = cls(self, self.config.get(name, {}))
            yield self.handlers[name].setup_handler()

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

        for name, handler in self.handlers.items():
            yield handler.teardown_handler()

    @inlineCallbacks
    def get_account_config(self, account_key):
        """Find the appropriate account config.

        TODO: Clean this up a bit.

        The account config we want is structured as follows:
            {
                (conversation_key, event_type): [
                        [handler, handler_config],
                        ...
                    ],
                ...
            }

        Unfortunately, this structure can't be stored directly in JSON.
        Therefore, what we get from Riak (or the static config, etc.) needs to
        be translated from this:
            [
                [[conversation_key, event_type], [
                        [handler, handler_config],
                        ...
                    ],
                ...
                ]
            ]

        Hence the juggling of eggs below.
        """
        if account_key not in self.account_config:
            user_account = yield self.vumi_api.account_store.get_user(
                account_key)
            event_handler_config = {}
            for k, v in (user_account.event_handler_config or
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
    @inlineCallbacks
    def setup_routing(self):
        # map conversation types to applications that deal with them
        self.conversation_mappings = self.config['conversation_mappings']
        self.upstream_transport = self.config['upstream_transport']
        self.optout_transport = self.config['optout_transport']
        self.vumi_api = yield VumiApi.from_config_async(self.config)

    @inlineCallbacks
    def find_application_for_msg(self, msg):
        md = GoMessageMetadata(self.vumi_api, msg)
        conversation_info = yield md.get_conversation_info()
        if conversation_info:
            conversation_key, conversation_type = conversation_info
            returnValue(self.conversation_mappings[conversation_type])

    @inlineCallbacks
    def find_application_for_event(self, event):
        """
        Look up the application for a given event by first looking up the
        outbound message that the event is for and then using that messages'
        batch to find which conversation it is associated with.
        """
        user_message_id = event.get('user_message_id')
        if user_message_id is None:
            log.error('Received event without user_message_id: %s' % (event,))
            return

        mdb = self.vumi_api.mdb
        outbound_message = yield mdb.outbound_messages.load(user_message_id)
        if outbound_message is None:
            log.error('Unable to find outbound message for event: %s' % (
                        event,))
            return

        batch = yield outbound_message.batch.get()
        if batch is None:
            log.error(
                'Outbound message without a batch id. Result of bad routing')
            return

        account_key = batch.metadata['user_account']
        user_api = self.vumi_api.get_user_api(account_key)
        conversations = user_api.conversation_store.conversations
        mr = conversations.index_lookup('batches', batch.key)
        [conv_key] = yield mr.get_keys()

        conv = yield user_api.get_wrapped_conversation(conv_key)
        if conv:
            returnValue(self.conversation_mappings[conv.conversation_type])

    @inlineCallbacks
    def dispatch_inbound_message(self, msg):
        application = yield self.find_application_for_msg(msg)
        if OptOutMiddleware.is_optout_message(msg):
            publisher = self.dispatcher.exposed_publisher[
                self.optout_transport]
            yield publisher.publish_message(msg)
        else:
            if application:
                publisher = self.dispatcher.exposed_publisher[application]
                yield publisher.publish_message(msg)
            else:
                # This often happens when we have a USSD code like *123*4#
                # and some random person dials *123*4*1# when that isn't
                # actually configured to route somewhere.
                log.warning(
                    'No application setup for inbound message: %s from %s' % (
                        msg['to_addr'], msg['transport_name']),
                    message=msg)

    @inlineCallbacks
    def dispatch_inbound_event(self, event):
        application = yield self.find_application_for_event(event)
        if application:
            publisher = self.dispatcher.exposed_event_publisher[application]
            yield publisher.publish_message(event)
        else:
            log.warning(
                'No application setup for inbount event type %s from %s' % (
                        event['event_type'], event['transport_name']),
                event=event)

    @inlineCallbacks
    def dispatch_outbound_message(self, msg):
        pub = self.dispatcher.transport_publisher[self.upstream_transport]
        yield pub.publish_message(msg)
