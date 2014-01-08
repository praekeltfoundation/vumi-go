from zope.interface import implements
from twisted.internet.defer import (
    inlineCallbacks, returnValue, maybeDeferred, gatherResults)

from vumi import log
from vumi.worker import BaseWorker
from vumi.application import ApplicationWorker
from vumi.blinkenlights.metrics import MetricManager
from vumi.config import IConfigData, ConfigText, ConfigDict, ConfigField
from vumi.connectors import IgnoreMessage

from go.config import get_conversation_definition
from go.vumitools.api import VumiApiCommand, VumiApi, VumiApiEvent
from go.vumitools.metrics import AccountMetric
from go.vumitools.utils import MessageMetadataHelper


class ConfigConversation(ConfigField):
    pass


class ConfigRouter(ConfigField):
    pass


class GoWorkerConfigData(object):
    implements(IConfigData)

    def __init__(self, static_config, dynamic_config):
        self._static_config = static_config
        self._dynamic_config = dynamic_config

    def get(self, field_name, default):
        if field_name in self._dynamic_config:
            return self._dynamic_config[field_name]
        return self._static_config.get(field_name, default)

    def has_key(self, field_name):
        if field_name in self._dynamic_config:
            return True
        return self._static_config.has_key(field_name)


class GoWorkerConfigMixin(object):
    worker_name = ConfigText(
        "Name of this worker.", required=True, static=True)
    metrics_prefix = ConfigText(
        "Metric name prefix.", default='go.', static=True)
    riak_manager = ConfigDict("Riak config.", static=True)
    redis_manager = ConfigDict("Redis config.", static=True)

    api_routing = ConfigDict("AMQP config for API commands.", static=True)
    app_event_routing = ConfigDict("AMQP config for app events.", static=True)


class GoWorkerMixin(object):
    redis = None
    manager = None
    control_consumer = None

    def _go_setup_vumi_api(self, config):
        api_config = {
            'riak_manager': config.riak_manager,
            'redis_manager': config.redis_manager,
            }
        d = VumiApi.from_config_async(api_config, self._amqp_client)

        def cb(vumi_api):
            self.vumi_api = vumi_api
            self.redis = vumi_api.redis
            self.manager = vumi_api.manager
        return d.addCallback(cb)

    def _go_setup_command_consumer(self, config):
        api_routing_config = VumiApiCommand.default_routing_config()
        if config.api_routing:
            api_routing_config.update(config.api_routing)
        d = self.consume(
            '%s.control' % (self.worker_name,),
            self.consume_control_command,
            exchange_name=api_routing_config['exchange'],
            exchange_type=api_routing_config['exchange_type'],
            message_class=VumiApiCommand)
        return d.addCallback(lambda r: setattr(self, 'control_consumer', r))

    def _go_setup_event_publisher(self, config):
        app_event_routing_config = VumiApiEvent.default_routing_config()
        if config.app_event_routing:
            app_event_routing_config.update(config.app_event_routing)
        d = self.publish_to(app_event_routing_config['routing_key'])
        return d.addCallback(lambda r: setattr(self, 'app_event_publisher', r))

    @inlineCallbacks
    def _go_setup_worker(self):
        self._metrics_conversations = set()
        self._cache_recon_conversations = set()
        config = self.get_static_config()
        if config.worker_name is not None:
            self.worker_name = config.worker_name

        self.metrics = yield self.start_publisher(
            MetricManager, config.metrics_prefix)

        yield self._go_setup_vumi_api(config)
        yield self._go_setup_event_publisher(config)
        yield self._go_setup_command_consumer(config)

    @inlineCallbacks
    def _go_teardown_worker(self):
        # Sometimes something else closes our Redis connection.
        if self.redis is not None:
            yield self.redis.close_manager()
        if self.control_consumer is not None:
            yield self.control_consumer.stop()
            self.control_consumer = None
        self.metrics.stop()

    def get_user_api(self, user_account_key):
        return self.vumi_api.get_user_api(user_account_key)

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
            return self.process_unknown_cmd(cmd_method_name, *args, **kwargs)

    @inlineCallbacks
    def process_command_collect_metrics(self, conversation_key,
                                        user_account_key):
        key_tuple = (conversation_key, user_account_key)
        if key_tuple in self._metrics_conversations:
            log.info("Ignoring conversation %s for user %s because the "
                     "previous collection run is still going." % (
                         conversation_key, user_account_key))
            return
        self._metrics_conversations.add(key_tuple)
        user_api = self.get_user_api(user_account_key)
        yield self.collect_metrics(user_api, conversation_key)
        self._metrics_conversations.remove(key_tuple)

    @inlineCallbacks
    def process_command_reconcile_cache(self, conversation_key,
                                        user_account_key):
        key_tuple = (conversation_key, user_account_key)
        if key_tuple in self._cache_recon_conversations:
            log.info("Ignoring conversation %s for user %s because the "
                     "previous cache recon run is still going." % (
                         conversation_key, user_account_key))
            return
        self._cache_recon_conversations.add(key_tuple)
        user_api = self.get_user_api(user_account_key)
        yield self.reconcile_cache(user_api, conversation_key)
        self._cache_recon_conversations.remove(key_tuple)

    def process_unknown_cmd(self, method_name, *args, **kwargs):
        log.error("Unknown vumi API command: %s(%s, %s)" % (
            method_name, args, kwargs))

    @inlineCallbacks
    def reconcile_cache(self, user_api, conversation_key, delta=0.01):
        """Reconcile the cached values for the conversation.

        Checks whether caches for a conversation are off by a given
        delta and if so, initiates a full cache reconciliation.

        :param VumiUserApi user_api:
            The Api for this user
        :param str conversation_key:
            The key of the conversation to reconcile
        :param float delta:
            If the key count difference between the message_store and
            the cache is bigger than the delta a reconciliation is initiated.
        """
        conv = yield user_api.get_wrapped_conversation(conversation_key)
        if conv is None:
            log.error('Conversation does not exist: %s' % (conversation_key,))
            return

        log.msg('Reconciling cache for %s' % (conversation_key,))
        message_store = user_api.api.mdb
        if (yield message_store.needs_reconciliation(conv.batch.key, delta)):
            yield message_store.reconcile_cache(conv.batch.key)
        log.msg('Cache reconciled for %s' % (conversation_key,))

    @inlineCallbacks
    def get_contact_for_message(self, message, create=True):
        msg_mdh = self.get_metadata_helper(message)

        if not msg_mdh.has_user_account():
            # If we have no user account we can't look up contacts.
            return

        user_api = msg_mdh.get_user_api()
        delivery_class = user_api.delivery_class_for_msg(message)
        contact = yield user_api.contact_store.contact_for_addr(
            delivery_class, message.user(), create=create)
        returnValue(contact)

    def get_conversation(self, user_account_key, conversation_key):
        user_api = self.get_user_api(user_account_key)
        return user_api.get_wrapped_conversation(conversation_key)

    def get_router(self, user_account_key, router_key):
        user_api = self.get_user_api(user_account_key)
        return user_api.get_router(router_key)

    def get_metadata_helper(self, msg):
        return MessageMetadataHelper(self.vumi_api, msg)

    @inlineCallbacks
    def find_outboundmessage_for_event(self, event):
        user_message_id = event.get('user_message_id')
        if user_message_id is None:
            log.error('Received event without user_message_id: %s' % (event,))
            return

        msg = yield self.vumi_api.mdb.outbound_messages.load(user_message_id)
        if msg is None:
            log.error('Unable to find message for event: %s' % (event,))

        returnValue(msg)

    @inlineCallbacks
    def find_message_for_event(self, event):
        outbound_message = yield self.find_outboundmessage_for_event(event)
        if outbound_message:
            returnValue(outbound_message.msg)

    @inlineCallbacks
    def find_inboundmessage_for_reply(self, reply):
        user_message_id = reply.get('in_reply_to')
        if user_message_id is None:
            log.error('Received reply without in_reply_to: %s' % (reply,))
            return

        msg = yield self.vumi_api.mdb.inbound_messages.load(user_message_id)
        if msg is None:
            log.error('Unable to find message for reply: %s' % (reply,))

        returnValue(msg)

    @inlineCallbacks
    def find_message_for_reply(self, reply):
        inbound_message = yield self.find_inboundmessage_for_reply(reply)
        if inbound_message:
            returnValue(inbound_message.msg)

    def event_for_message(self, message, event_type, content):
        msg_mdh = self.get_metadata_helper(message)
        return VumiApiEvent.event(msg_mdh.get_account_key(),
                                  msg_mdh.get_conversation_key(),
                                  event_type, content)

    def trigger_event(self, message, event_type, content):
        event = self.event_for_message(message, event_type, content)
        return self.publish_app_event(event)

    def publish_app_event(self, event):
        self.app_event_publisher.publish_message(event)

    def publish_account_metric(self, acc_key, store, name, value, agg=None):
        metric = AccountMetric(acc_key, store, name, agg)
        metric.oneshot(self.metrics, value)

    @inlineCallbacks
    def publish_conversation_metrics(self, user_api, conversation_key):
        conv = yield user_api.get_conversation(conversation_key)

        conv_type = conv.conversation_type
        conv_def = get_conversation_definition(conv_type, conv)

        yield gatherResults([
            m.oneshot(self.metrics, user_api=user_api)
            for m in conv_def.get_metrics()])

    def collect_metrics(self, user_api, conversation_key):
        return self.publish_conversation_metrics(user_api, conversation_key)

    def add_conv_to_msg_options(self, conv, msg_options):
        helper_metadata = msg_options.setdefault('helper_metadata', {})
        conv.set_go_helper_metadata(helper_metadata)
        return msg_options


class GoApplicationMixin(GoWorkerMixin):
    def get_config_data_for_conversation(self, conversation):
        config = conversation.config.copy()
        config["conversation"] = conversation
        return GoWorkerConfigData(self.config, config)

    def get_config_for_conversation(self, conversation):
        # If the conversation isn't running, we want to ignore the message
        # instead of getting the config.
        if not conversation.running():
            raise IgnoreMessage(
                "Conversation '%s' not running." % (conversation.key,))
        config_data = self.get_config_data_for_conversation(conversation)
        return self.CONFIG_CLASS(config_data)

    @inlineCallbacks
    def get_message_config(self, msg):
        # By the time we get an event here, the metadata has already been
        # populated for us from the original message by the routing table
        # dispatcher.
        msg_mdh = self.get_metadata_helper(msg)
        conversation = yield msg_mdh.get_conversation()

        returnValue(self.get_config_for_conversation(conversation))

    @inlineCallbacks
    def process_command_start(self, user_account_key, conversation_key):
        log.info("Starting conversation '%s' for user '%s'." % (
            conversation_key, user_account_key))
        conv = yield self.get_conversation(user_account_key, conversation_key)
        if conv is None:
            log.warning(
                "Trying to start missing conversation '%s' for user '%s'." % (
                    conversation_key, user_account_key))
            return
        if not conv.starting():
            status = conv.get_status()
            log.warning(
                "Trying to start conversation '%s' for user '%s' with invalid "
                "status: %s" % (conversation_key, user_account_key, status))
            return
        conv.set_status_started()
        yield conv.save()

    @inlineCallbacks
    def process_command_stop(self, user_account_key, conversation_key):
        conv = yield self.get_conversation(user_account_key, conversation_key)
        if conv is None:
            log.warning(
                "Trying to stop missing conversation '%s' for user '%s'." % (
                    conversation_key, user_account_key))
            return
        if not conv.stopping():
            status = conv.get_status()
            log.warning(
                "Trying to stop conversation '%s' for user '%s' with invalid "
                "status: %s" % (conversation_key, user_account_key, status))
            return
        conv.set_status_stopped()
        yield conv.save()

    @inlineCallbacks
    def process_command_send_message(self, user_account_key, conversation_key,
                                     command_data, **kwargs):
        if kwargs:
            log.info("Received unexpected command args: %s" % (kwargs,))
        conv = yield self.get_conversation(user_account_key, conversation_key)
        if conv is None:
            log.warning("Cannot find conversation '%s' for user '%s'." % (
                conversation_key, user_account_key))
            return

        log.info('Processing send_message: %s' % kwargs)
        to_addr = command_data['to_addr']
        content = command_data['content']
        msg_options = command_data['msg_options']
        in_reply_to = msg_options.pop('in_reply_to', None)
        self.add_conv_to_msg_options(conv, msg_options)
        if in_reply_to:
            msg = yield self.vumi_api.mdb.get_inbound_message(in_reply_to)
            if msg:
                yield self.reply_to(
                    msg, content,
                    helper_metadata=msg_options['helper_metadata'])
            else:
                log.warning('Unable to reply, message %s does not exist.' % (
                    in_reply_to))
        else:
            yield self.send_to(
                to_addr, content, endpoint='default', **msg_options)


class GoRouterMixin(GoWorkerMixin):
    def get_config_data_for_router(self, router):
        config = router.config.copy()
        config["router"] = router
        return GoWorkerConfigData(self.config, config)

    def get_config_for_router(self, router):
        # If the router isn't running, we want to ignore the message instead of
        # getting the config.
        if not router.running():
            raise IgnoreMessage("Router '%s' not running." % (router.key,))
        config_data = self.get_config_data_for_router(router)
        return self.CONFIG_CLASS(config_data)

    @inlineCallbacks
    def get_message_config(self, msg):
        # By the time we get an event here, the metadata has already been
        # populated for us from the original message by the routing table
        # dispatcher.
        msg_mdh = self.get_metadata_helper(msg)
        router = yield msg_mdh.get_router()

        returnValue(self.get_config_for_router(router))

    @inlineCallbacks
    def process_command_start(self, user_account_key, router_key):
        log.info("Starting router '%s' for user '%s'." % (
            router_key, user_account_key))
        router = yield self.get_router(user_account_key, router_key)
        if router is None:
            log.warning(
                "Trying to start missing router '%s' for user '%s'." % (
                    router_key, user_account_key))
            return
        if not router.starting():
            log.warning(
                "Trying to start router '%s' for user '%s' with invalid "
                "status: %s" % (router_key, user_account_key, router.status))
            return
        router.set_status_started()
        yield router.save()

    @inlineCallbacks
    def process_command_stop(self, user_account_key, router_key):
        router = yield self.get_router(user_account_key, router_key)
        if router is None:
            log.warning(
                "Trying to stop missing router '%s' for user '%s'." % (
                    router_key, user_account_key))
            return
        if not router.stopping():
            log.warning(
                "Trying to stop router '%s' for user '%s' with invalid "
                "status: %s" % (router_key, user_account_key, router.status))
            return
        router.set_status_stopped()
        yield router.save()


class GoApplicationConfigMixin(GoWorkerConfigMixin):
    conversation = ConfigConversation(
        "Conversation instance for this message", required=False)


class GoApplicationConfig(ApplicationWorker.CONFIG_CLASS,
                          GoApplicationConfigMixin):
    pass


class GoApplicationWorker(GoApplicationMixin, ApplicationWorker):
    """
    A base class for Vumi Go application worker.

    Configuration parameters:

    :type worker_name: str
    :param worker_name:
        The name of this worker, used for receiving control messages.

    """
    CONFIG_CLASS = GoApplicationConfig

    worker_name = None

    def setup_application(self):
        return self._go_setup_worker()

    def teardown_application(self):
        return self._go_teardown_worker()

    def _publish_message(self, message, endpoint_name=None):
        if not self.get_metadata_helper(message).get_conversation_info:
            log.error(
                "Conversation metadata missing for message for %s: %s" % (
                    type(self).__name__, message))
        return super(GoApplicationWorker, self)._publish_message(
            message, endpoint_name)


class GoRouterConfigMixin(GoWorkerConfigMixin):
    ri_connector_name = ConfigText(
        "The name of the receive_inbound connector.",
        required=True, static=True)
    ro_connector_name = ConfigText(
        "The name of the receive_outbound connector.",
        required=True, static=True)
    router = ConfigRouter(
        "Router instance for this message", required=False)


class GoRouterConfig(BaseWorker.CONFIG_CLASS, GoRouterConfigMixin):
    pass


class GoRouterWorker(GoRouterMixin, BaseWorker):
    """
    A base class for Vumi Go router workers.
    """
    CONFIG_CLASS = GoRouterConfig

    worker_name = None

    def setup_router(self):
        return self._go_setup_worker()

    def teardown_router(self):
        return self._go_teardown_worker()

    def setup_worker(self):
        d = maybeDeferred(self.setup_router)
        d.addCallback(lambda r: self.unpause_connectors())
        return d

    def teardown_worker(self):
        self.pause_connectors()
        return self.teardown_router()

    def get_config(self, msg, ctxt=None):
        return self.get_message_config(msg)

    def handle_inbound(self, config, msg):
        raise NotImplementedError()

    def handle_outbound(self, config, msg):
        raise NotImplementedError()

    def handle_event(self, config, event, conn_name):
        log.debug("Handling event: %s" % (event,))
        # To avoid circular import.
        from go.vumitools.routing import RoutingMetadata
        endpoint = RoutingMetadata(event).next_router_endpoint()
        self.publish_event(event, endpoint=endpoint)

    def _mkhandler(self, handler_func, connector_name):
        def handler(msg):
            d = self.get_config(msg)
            d.addCallback(handler_func, msg, connector_name)
            return d
        return handler

    def setup_connectors(self):
        config = self.get_static_config()
        self._ri_conn_name = config.ri_connector_name
        self._ro_conn_name = config.ro_connector_name

        def add_ri_handlers(connector, connector_name):
            connector.set_default_inbound_handler(
                self._mkhandler(self.handle_inbound, connector_name))
            connector.set_default_event_handler(
                self._mkhandler(self.handle_event, connector_name))
            return connector

        def add_ro_handlers(connector, connector_name):
            connector.set_default_outbound_handler(
                self._mkhandler(self.handle_outbound, connector_name))
            return connector

        deferreds = []
        d = self.setup_ri_connector(self._ri_conn_name)
        d.addCallback(add_ri_handlers, self._ri_conn_name)
        deferreds.append(d)

        d = self.setup_ro_connector(self._ro_conn_name)
        d.addCallback(add_ro_handlers, self._ro_conn_name)
        deferreds.append(d)

        return gatherResults(deferreds)

    def publish_inbound(self, msg, endpoint):
        return self.connectors[self._ro_conn_name].publish_inbound(
            msg, endpoint)

    def publish_outbound(self, msg, endpoint):
        return self.connectors[self._ri_conn_name].publish_outbound(
            msg, endpoint)

    def publish_event(self, event, endpoint):
        return self.connectors[self._ro_conn_name].publish_event(
            event, endpoint)
