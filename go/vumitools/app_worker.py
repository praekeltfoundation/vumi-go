from zope.interface import implements
from twisted.internet import reactor
from twisted.internet.defer import (
    inlineCallbacks, returnValue, maybeDeferred, gatherResults)

from vumi import log
from vumi.message import TransportUserMessage
from vumi.worker import BaseWorker
from vumi.application import ApplicationWorker
from vumi.blinkenlights.metrics import MetricPublisher, Metric
from vumi.config import (
    IConfigData, ConfigText, ConfigDict, ConfigField, ConfigFloat)
from vumi.connectors import IgnoreMessage

from go.config import get_conversation_definition
from go.vumitools.api import (
    VumiApiCommand, VumiApi, VumiApiEvent, ApiCommandPublisher,
    ApiEventPublisher)
from go.vumitools.metrics import (
    get_account_metric_prefix, get_conversation_metric_prefix)
from go.vumitools.model_object_cache import ModelObjectCache
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

    def __contains__(self, field_name):
        return self.has_key(field_name)


class GoWorkerConfigMixin(object):
    worker_name = ConfigText(
        "Name of this worker.", required=True, static=True)
    riak_manager = ConfigDict("Riak config.", static=True)
    redis_manager = ConfigDict("Redis config.", static=True)
    conversation_cache_ttl = ConfigFloat(
        "TTL (in seconds) for cached conversations. If less than or equal to"
        " zero, conversations will not be cached.",
        static=True, default=5)


class GoWorkerMixin(object):
    redis = None
    manager = None
    control_consumer = None

    def _go_setup_vumi_api(self, config):
        api_config = {
            'riak_manager': config.riak_manager,
            'redis_manager': config.redis_manager,
            }
        d = VumiApi.from_config_async(
            api_config, self.command_publisher, self.metric_publisher)

        def cb(vumi_api):
            self.vumi_api = vumi_api
            self.redis = vumi_api.redis
            self.manager = vumi_api.manager
        return d.addCallback(cb)

    def _go_setup_command_consumer(self, config):
        d = self.consume(
            '%s.control' % (self.worker_name,),
            self.consume_control_command,
            message_class=VumiApiCommand, prefetch_count=1)
        return d.addCallback(lambda r: setattr(self, 'control_consumer', r))

    def _go_setup_command_publisher(self, config):
        d = self.start_publisher(ApiCommandPublisher)
        return d.addCallback(lambda r: setattr(self, 'command_publisher', r))

    def _go_setup_event_publisher(self, config):
        d = self.start_publisher(ApiEventPublisher)
        return d.addCallback(lambda r: setattr(self, 'app_event_publisher', r))

    @inlineCallbacks
    def _go_setup_worker(self):
        self._metrics_conversations = set()
        config = self.get_static_config()
        if config.worker_name is not None:
            self.worker_name = config.worker_name

        # Not all workers need this, but it's cheap if unused and easier to put
        # here than a bunch of more specific places.
        self._conversation_cache = ModelObjectCache(
            reactor, config.conversation_cache_ttl)

        self.metric_publisher = yield self.start_publisher(MetricPublisher)

        yield self._go_setup_command_publisher(config)
        yield self._go_setup_event_publisher(config)
        yield self._go_setup_vumi_api(config)
        yield self._go_setup_command_consumer(config)

    @inlineCallbacks
    def _go_teardown_worker(self):
        yield self._conversation_cache.cleanup()
        if self.control_consumer is not None:
            yield self.control_consumer.stop()
            self.control_consumer = None
        yield self.vumi_api.close()

    def get_user_api(self, user_account_key):
        return self.vumi_api.get_user_api(user_account_key)

    def _ignore_message(self, failure, msg):
        failure.trap(IgnoreMessage)
        log.debug("Ignoring msg due to %r: %r" % (failure.value, msg))

    def consume_control_command(self, command_message):
        """
        Handle a VumiApiCommand message that has arrived.

        :type command_message: VumiApiCommand
        :param command_message:
            The command message received for this application.
        """
        cmd_method_name = 'process_command_%(command)s' % command_message
        command_id = command_message['command_id']
        args = command_message['args']
        kwargs = command_message['kwargs']
        cmd_method = getattr(self, cmd_method_name, None)
        if cmd_method:
            d = maybeDeferred(cmd_method, command_id, *args, **kwargs)
            d.addErrback(self._ignore_message, command_message)
            return d
        else:
            return self.process_unknown_cmd(
                cmd_method_name, command_id, *args, **kwargs)

    @inlineCallbacks
    def process_command_collect_metrics(self, cmd_id, conversation_key,
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

    def process_unknown_cmd(self, method_name, command_id, *args, **kwargs):
        log.error("Unknown vumi API command: %s(%s, %s) id=%s" % (
            method_name, args, kwargs, command_id))

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
        return self._conversation_cache.get_model(
            user_api.get_wrapped_conversation, conversation_key)

    def get_router(self, user_account_key, router_key):
        user_api = self.get_user_api(user_account_key)
        return user_api.get_router(router_key)

    def get_metadata_helper(self, msg):
        return MessageMetadataHelper(
            self.vumi_api, msg, conversation_cache=self._conversation_cache)

    @inlineCallbacks
    def _find_outboundmessage_for_event(self, event):
        user_message_id = event.get('user_message_id')
        if user_message_id is None:
            log.error('Received event without user_message_id: %s' % (event,))
            return

        opms = self.vumi_api.get_operational_message_store()
        msg = yield opms.get_outbound_message(user_message_id)
        if msg is None:
            log.error('Unable to find message for event: %s' % (event,))

        returnValue(msg)

    _EVENT_OUTBOUND_CACHE_KEY = "outbound_message_json"

    def _get_outbound_from_event_cache(self, event):
        """
        Retrieve outbound message from the cache on an event.
        """
        if self._EVENT_OUTBOUND_CACHE_KEY not in event.cache:
            return False, None
        outbound_json = event.cache[self._EVENT_OUTBOUND_CACHE_KEY]
        if outbound_json is None:
            return True, None
        return True, TransportUserMessage.from_json(outbound_json)

    def _store_outbound_in_event_cache(self, event, outbound):
        """
        Store an outbound message in the cache on an event.
        """
        if outbound is None:
            event.cache[self._EVENT_OUTBOUND_CACHE_KEY] = None
        else:
            event.cache[self._EVENT_OUTBOUND_CACHE_KEY] = outbound.to_json()

    @inlineCallbacks
    def find_message_for_event(self, event):
        hit, outbound_msg = self._get_outbound_from_event_cache(event)
        if hit:
            returnValue(outbound_msg)

        outbound_msg = yield self._find_outboundmessage_for_event(event)
        self._store_outbound_in_event_cache(event, outbound_msg)
        returnValue(outbound_msg)

    @inlineCallbacks
    def find_message_for_reply(self, reply):
        user_message_id = reply.get('in_reply_to')
        if user_message_id is None:
            log.error('Received reply without in_reply_to: %s' % (reply,))
            return

        opms = self.vumi_api.get_operational_message_store()
        msg = yield opms.get_inbound_message(user_message_id)
        if msg is None:
            log.error('Unable to find message for reply: %s' % (reply,))

        returnValue(msg)

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

    def get_account_metric_manager(self, account_key, store_name):
        # TODO: Move this to an API.
        prefix = get_account_metric_prefix(account_key, store_name)
        return self.vumi_api.get_metric_manager(prefix)

    def get_conversation_metric_manager(self, conv):
        # TODO: Move this to an API.
        prefix = get_conversation_metric_prefix(conv)
        return self.vumi_api.get_metric_manager(prefix)

    def publish_account_metric(self, acc_key, store, name, value, agg=None):
        # TODO: Collect the oneshot metrics and then publish all at once?
        if agg is not None:
            agg = [agg]
        metric = Metric(name, agg)
        metrics = self.get_account_metric_manager(acc_key, store)
        metrics.oneshot(metric, value)
        metrics.publish_metrics()

    @inlineCallbacks
    def publish_conversation_metrics(self, user_api, conversation_key):
        conv = yield user_api.get_conversation(conversation_key)
        metrics = self.get_conversation_metric_manager(conv)

        conv_type = conv.conversation_type
        conv_def = get_conversation_definition(conv_type, conv)

        for metric in conv_def.get_metrics():
            value = yield metric.get_value(user_api)
            metrics.oneshot(metric.metric, value)

        metrics.publish_metrics()

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
    def process_command_start(self, cmd_id, user_account_key, conversation_key):
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
    def process_command_stop(self, cmd_id, user_account_key, conversation_key):
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
    def process_command_send_message(self, cmd_id, user_account_key,
                                     conversation_key, command_data, **kwargs):
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
            opms = self.vumi_api.get_operational_message_store()
            msg = yield opms.get_inbound_message(in_reply_to)
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
    def process_command_start(self, cmd_id, user_account_key, router_key):
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
    def process_command_stop(self, cmd_id, user_account_key, router_key):
        log.info("Stopping router '%s' for user '%s'." % (
            router_key, user_account_key))
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

    def handle_inbound(self, config, msg, conn_name):
        raise NotImplementedError()

    def handle_outbound(self, config, msg, conn_name):
        raise NotImplementedError()

    def handle_event(self, config, event, conn_name):
        log.debug("Handling event: %s" % (event,))
        # To avoid circular import.
        from go.vumitools.routing import RoutingMetadata
        endpoint = RoutingMetadata(event).next_router_endpoint()
        if endpoint is not None:
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
