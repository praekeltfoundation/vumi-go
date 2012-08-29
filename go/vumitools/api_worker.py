# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application import ApplicationWorker
from vumi.dispatchers.base import BaseDispatchRouter
from vumi.utils import load_class_by_string
from vumi import log
from vumi.middleware.tagger import TaggingMiddleware

from go.vumitools.api import VumiApi, VumiUserApi, VumiApiCommand, VumiApiEvent
from go.vumitools.middleware import OptOutMiddleware


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


class GoMessageMetadata(object):
    """Look up various bits of metadata for a Vumi Go message.

    We store metadata in two places:

    1. Keys into the various stores go into the message helper_metadata.
       This is helpful for preventing unnecessary duplicate lookups between
       workers.

    2. Objects retreived from those stores get stashed on the message object.
       This is helpful for preventing duplicate lookups within a worker.
       (Between different middlewares, for example.)
    """

    def __init__(self, vumi_api, message):
        self.vumi_api = vumi_api
        self.message = message

        # Easier access to metadata.
        message_metadata = message.get('helper_metadata', {})
        self._go_metadata = message_metadata.setdefault('go', {})

        # A place to store objects we don't want serialised.
        if not hasattr(message, '_store_objects'):
            message._store_objects = {}
        self._store_objects = message._store_objects

        # If we don't have a tag, we want to blow up early in some places.
        self.tag = TaggingMiddleware.map_msg_to_tag(message)

    @inlineCallbacks
    def _get_tag_info(self):
        if not self.tag:
            # Without a tag, there's no point in bothering.
            return

        if 'tag_info' in self._store_objects:
            # We already have this, no need to look it up.
            returnValue(self._store_objects['tag_info'])

        # Get it from the message store.
        tag_info = yield self.vumi_api.mdb.get_tag_info(self.tag)
        self._store_objects['tag_info'] = tag_info
        returnValue(tag_info)

    @inlineCallbacks
    def _find_batch(self):
        if 'batch' in self._store_objects:
            # We already have this, no need to look it up.
            returnValue(self._store_objects['batch'])

        if 'batch_key' in self._go_metadata:
            # We know what it is, we just need to get it.
            batch = yield self.vumi_api.mdb.get_batch(
                self._go_metadata['batch_key'])
            self._store_objects['batch'] = batch
            returnValue(batch)

        # Look it up from the tag, assuming we have one.
        tag_info = yield self._get_tag_info()
        if tag_info:
            batch = yield tag_info.current_batch.get()
            self._store_objects['batch'] = batch
            self._go_metadata['batch_key'] = batch.key
            returnValue(batch)

    @inlineCallbacks
    def get_batch_key(self):
        if 'batch_key' not in self._go_metadata:
            # We're calling _find_batch() for the side effect, which is to put
            # the batch key in the metadata if there is one.
            yield self._find_batch()
        returnValue(self._go_metadata.get('batch_key'))

    @inlineCallbacks
    def _find_account_key(self):
        if 'user_account' in self._go_metadata:
            # We already have this, no need to look it up.
            returnValue(self._go_metadata['user_account'])

        # Look it up from the batch, assuming we can get one.
        batch = yield self._find_batch()
        if batch:
            user_account_key = batch.metadata['user_account']
            self._go_metadata['user_account'] = user_account_key
            returnValue(user_account_key)

    @inlineCallbacks
    def get_account_key(self):
        if 'user_account' not in self._go_metadata:
            # We're calling _find_account_key() for the side effect, which is
            # to put the account key in the metadata if there is one.
            yield self._find_account_key()
        returnValue(self._go_metadata.get('user_account'))

    @inlineCallbacks
    def _get_conversation_store(self):
        if 'conv_store' in self._store_objects:
            returnValue(self._store_objects['conv_store'])

        # We need an account key to get at a conversation.
        account_key = yield self.get_account_key()
        if not account_key:
            return

        user_api = VumiUserApi(self.vumi_api, account_key)
        conv_store = user_api.conversation_store
        self._store_objects['conv_store'] = conv_store
        returnValue(conv_store)

    @inlineCallbacks
    def _find_conversation(self):
        if 'conversation' in self._store_objects:
            # We already have this, no need to look it up.
            returnValue(self._store_objects['conversation'])

        # We need a conversation store.
        conv_store = yield self._get_conversation_store()
        if not conv_store:
            return

        if 'conversation_key' in self._go_metadata:
            # We know what it is, we just need to get it.
            conversation = yield conv_store.get_conversation_by_key(
                self._go_metadata['conversation_key'])
            returnValue(conversation)

        batch = yield self._find_batch()
        if not batch:
            # Without a batch, we can't get a conversation.
            return

        all_conversations = yield batch.backlinks.conversations(
            conv_store.manager)
        conversations = [c for c in all_conversations if not c.ended()]
        if not conversations:
            # No open conversations for this batch.
            return

        # We may have more than one conversation here.
        if len(conversations) > 1:
            conv_keys = [c.key for c in conversations]
            log.warning('Multiple conversations found '
                        'going with most recent: %r' % (conv_keys,))
        conversation = sorted(conversations, reverse=True,
                              key=lambda c: c.start_timestamp)[0]

        self._go_metadata['conversation_key'] = conversation.key
        self._go_metadata['conversation_type'] = conversation.conversation_type
        returnValue(conversation)

    @inlineCallbacks
    def get_conversation_info(self):
        if 'conversation_key' not in self._go_metadata:
            conv = yield self._find_conversation()
            if conv is None:
                # We couldn't find a conversation.
                return
        returnValue((self._go_metadata['conversation_key'],
                     self._go_metadata['conversation_type']))

    def set_conversation_info(self, conversation):
        self._go_metadata['conversation_key'] = conversation.key
        self._go_metadata['conversation_type'] = conversation.conversation_type


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
        self.api_event_consumer = None
        self.handler_config = self.config.get('event_handlers', {})
        self.account_handler_configs = self.config.get(
            'account_handler_configs', {})

    @inlineCallbacks
    def setup_application(self):
        self.handlers = {}

        self.api_command_publisher = yield self.publish_to('vumi.api')
        self.vumi_api = yield VumiApi.from_config_async(self.config)
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
    def setup_routing(self):
        # map conversation types to applications that deal with them
        self.conversation_mappings = self.config['conversation_mappings']
        self.upstream_transport = self.config['upstream_transport']
        self.optout_transport = self.config['optout_transport']

        # TODO: Fix this madness.
        self.vumi_api_d = VumiApi.from_config_async(self.config)
        self.vumi_api = None

    @inlineCallbacks
    def find_application_for_msg(self, msg):
        if self.vumi_api is None:
            self.vumi_api = yield self.vumi_api_d
        md = GoMessageMetadata(self.vumi_api, msg)
        conversation_info = yield md.get_conversation_info()
        if conversation_info:
            conversation_key, conversation_type = conversation_info
            returnValue(self.conversation_mappings[conversation_type])

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
                log.error('No application setup for inbound message '
                            'type: %s' % (msg,))

    @inlineCallbacks
    def dispatch_inbound_event(self, msg):
        application = yield self.find_application_for_msg(msg)
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
