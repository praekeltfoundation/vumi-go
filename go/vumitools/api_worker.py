# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application import ApplicationWorker
from vumi.utils import load_class_by_string
from vumi import log

from go.vumitools.api import (
    VumiApi, VumiApiCommand, VumiApiEvent, ApiCommandPublisher,
    ApiEventPublisher)


# TODO: None of these should be ApplicationWorker subclasses.


class CommandDispatcher(ApplicationWorker):
    """
    An application worker that forwards commands arriving on the Vumi Api queue
    to the relevant applications. It does this by using the command's
    worker_name parameter to construct the routing key.

    Configuration parameters:

    :param list worker_names:
        A list of known worker names that we can forward
        VumiApiCommands to.
    """

    # TODO: Make this not an ApplicationWorker.

    def validate_config(self):
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
            ApiCommandPublisher.routing_key, self.consume_control_command,
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

    :param dict event_handlers:
        A mapping from handler name to fully-qualified class name.
    """

    # TODO: Make this not an ApplicationWorker.

    def validate_config(self):
        self.api_event_consumer = None
        self.handler_config = self.config.get('event_handlers', {})
        self.account_handler_configs = self.config.get(
            'account_handler_configs', {})

    @inlineCallbacks
    def setup_application(self):
        self.handlers = {}

        self.api_command_publisher = yield self.start_publisher(
            ApiCommandPublisher)
        self.vumi_api = yield VumiApi.from_config_async(
            self.config, self.api_command_publisher)
        self.account_config = {}

        for name, handler_class in self.handler_config.items():
            cls = load_class_by_string(handler_class)
            self.handlers[name] = cls(self, self.config.get(name, {}))
            yield self.handlers[name].setup_handler()

        self.api_event_consumer = yield self.consume(
            ApiEventPublisher.routing_key, self.consume_api_event,
            message_class=VumiApiEvent)

    @inlineCallbacks
    def teardown_application(self):
        if self.api_event_consumer:
            yield self.api_event_consumer.stop()
            self.api_event_consumer = None

        for name, handler in self.handlers.items():
            yield handler.teardown_handler()

        yield self.vumi_api.cleanup()

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
            user_account = yield self.vumi_api.get_user_account(account_key)
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
