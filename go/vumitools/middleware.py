# -*- test-case-name: go.vumitools.tests.test_middleware -*-
import math
import re
import time

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall

from vumi.config import (
    ConfigBool, ConfigDict, ConfigFloat, ConfigInt, ConfigList, ConfigRiak,
    ConfigText)
from vumi.middleware.base import TransportMiddleware, BaseMiddleware
from vumi.middleware.message_storing import (
    StoringMiddleware, StoringMiddlewareConfig)
from vumi.middleware.tagger import TaggingMiddleware
from vumi.utils import normalize_msisdn
from vumi.blinkenlights.metrics import (
    MetricPublisher, Count, Metric, MetricManager, AVG, SUM)
from vumi.errors import ConfigError
from vumi.persist.txredis_manager import TxRedisManager

from go.vumitools.api import VumiApi
from go.vumitools.model_object_cache import ModelObjectCache
from go.vumitools.utils import MessageMetadataHelper


class NormalizeMsisdnMiddlewareConfig(TransportMiddleware.CONFIG_CLASS):
    """
    NormalizeMsisdnMiddleware configuration options.
    """

    country_code = ConfigText(
        "Country code prefix to normalize.",
        required=True, static=True)

    strip_plus = ConfigBool(
        "Whether to strip leading + signs.",
        default=False, static=True)


class NormalizeMsisdnMiddleware(TransportMiddleware):

    CONFIG_CLASS = NormalizeMsisdnMiddlewareConfig

    def setup_middleware(self):
        self.country_code = self.config.country_code
        self.strip_plus = self.config.strip_plus

    def _normalize_msisdn(self, addr, country_code, strip_plus):
        if addr is None:
            return addr
        addr = normalize_msisdn(addr, country_code=country_code)
        if strip_plus:
            addr = addr.lstrip('+')
        return addr

    def handle_inbound(self, message, endpoint):
        message['from_addr'] = self._normalize_msisdn(
            message.get('from_addr'), country_code=self.country_code,
            strip_plus=False)
        return message

    def handle_outbound(self, message, endpoint):
        message['to_addr'] = self._normalize_msisdn(
            message.get('to_addr'), country_code=self.country_code,
            strip_plus=self.strip_plus)
        return message


class OptOutMiddlewareConfig(BaseMiddleware.CONFIG_CLASS):
    """
    OptOutMiddleware configuration options.
    """

    redis_manager = ConfigDict(
        "Redis configuration parameters", default={}, static=True)

    riak_manager = ConfigRiak(
        "Riak configuration parameters. Must contain at least a bucket_prefix"
        " key", required=True, static=True)

    optout_keywords = ConfigList(
        "List of opt out keywords",
        default=(), static=True)

    case_sensitive = ConfigBool(
        "Whether opt out keywords are case sensitive.",
        default=False, static=True)


class OptOutMiddleware(BaseMiddleware):

    CONFIG_CLASS = OptOutMiddlewareConfig

    @inlineCallbacks
    def setup_middleware(self):
        self.vumi_api = yield VumiApi.from_config_async({
            "riak_manager": self.config.riak_manager,
            "redis_manager": self.config.redis_manager,
        })
        self.case_sensitive = self.config.case_sensitive
        self.optout_keywords = set(
            self.casing(word) for word in self.config.optout_keywords)

    def teardown_middleware(self):
        return self.vumi_api.close()

    def casing(self, word):
        if not self.case_sensitive:
            return word.lower()
        return word

    @inlineCallbacks
    def handle_inbound(self, message, endpoint):
        optout_disabled = False
        msg_mdh = MessageMetadataHelper(self.vumi_api, message)
        if msg_mdh.tag is not None:
            tagpool_metadata = yield msg_mdh.get_tagpool_metadata()
            optout_disabled = tagpool_metadata.get(
                'disable_global_opt_out', False)
        keyword = (message['content'] or '').strip()
        helper_metadata = message['helper_metadata']
        optout_metadata = helper_metadata.setdefault(
            'optout', {'optout': False})

        if (not optout_disabled
                and self.casing(keyword) in self.optout_keywords):
            optout_metadata['optout'] = True
            optout_metadata['optout_keyword'] = self.casing(keyword)
        returnValue(message)

    @staticmethod
    def is_optout_message(message):
        return message['helper_metadata'].get('optout', {}).get('optout')


class TimeMetric(Metric):
    """
    A time-based metric that fires both sums and averages.
    """
    DEFAULT_AGGREGATORS = [AVG, SUM]


class MetricsMiddlewareConfig(BaseMiddleware.CONFIG_CLASS):

    manager_name = ConfigText(
        "The name of the metrics publisher, this is used for the"
        " MetricManager publisher and all metric names will be prefixed"
        " with it.",
        required=True, static=True)

    redis_manager = ConfigDict(
        "Redis configuration parameters", default={}, static=True)

    count_suffix = ConfigText(
        "Defaults to 'count'. This is the suffix appended to all counters. If"
        " a message is received on connector 'foo', counters are published on"
        " '<manager_name>.foo.inbound.<count_suffix>'",
        default='count', static=True)

    response_time_suffix = ConfigText(
        "Defaults to 'response_time'. This is the suffix appended to all"
        " average response time metrics. If a message is received its"
        " `message_id` is stored and when a reply for the given `message_id`"
        " is sent out, the timestamps are compared and a averaged metric is"
        " published.",
        default='response_time', static=True)

    session_time_suffix = ConfigText(
        "Defaults to 'session_time'. This is the suffix appended to all"
        " session timer metrics. When a session starts the current time is"
        " stored under the `from_addr` and when the session ends, the"
        " duration of the session is published.",
        default='session_time', static=True)

    session_billing_unit = ConfigFloat(
        "Defaults to ``null``. Some networks charge for sessions per unit of"
        " time or part there of. This means it might be useful, for example,"
        " to record the session duration rounded to the nearest 20 seconds."
        " Setting `session_billing_unit` to a number fires an additional"
        " metric whenever the session duration metric is fired. The new"
        " metric records the duration rounded up to the next"
        " `session_billing_unit`.",
        required=False, static=True)

    provider_metrics = ConfigBool(
        "Defaults to ``false``. Set to ``true`` to fire per-operator metrics.",
        default=False, static=True)

    tagpools = ConfigDict(
        """
        A dictionary defining which tag pools and tags should be tracked.
        E.g.::

            tagpools:
                pool1:
                    track_pool: true
                    track_all_tags: true
                pool2:
                    track_tags: ["tagA"]

        This tracks `pool1` but not `pool2` and tracks all tags from `pool`
        and the tag `tagB` (from `pool2`). If this configuration
        option is missing or empty, no tag or tag pool metrics are produced.
        """,
        required=False, static=True)

    max_session_time = ConfigInt(
        "How long to keep the session time timestamp for. Any session"
        " duration longer than this is not recorded. Defaults to 600 seconds.",
        default=600, static=True)

    op_mode = ConfigText(
        """
        What mode to operate in, options are `passive` or `active`.
        Defaults to passive.
        *passive*:  assumes the middleware connector names are to be used as
                    the names for metrics publishing.
        *active*:   assumes that the individual messages are to be inspected
                    for their `transport_name` values.

        NOTE:   This does not apply for events or failures, the connectors
                names are always used for those since those message types are
                not guaranteed to have a `transport_name` value.
        """,
        default="passive", static=True)

    metric_connectors = ConfigList(
        "List of connector names to fire metrics for. Useful for when"
        " wrapping dispatchers with many connectors, only a subset of which"
        " should generate metrics. Defaults to all connectors.",
        required=False, static=True)


class MetricsMiddleware(BaseMiddleware):
    """
    Middleware that publishes metrics on messages flowing through.

    For each transport it tracks:

    * The number of messages sent and received.
    * The time taken to respond to each reply.
    * The number of sessions started.
    * The length of each session.

    For each network operator it tracks:

    * The number of messages sent and received.
    * The number of sessions started.
    * The length of each session.

    The network operator is determined by examining each message. If the
    network operator is not detected by the transport, consider using network
    operator detecting middleware to provide it.

    Network operator metrics must be enabled by setting ``provider_metrics`` to
    ``true``.

    For each selected tag or tag pool it tracks:

    * The number of messages sent and received.
    * The number of sessions started.
    * The length of each session.

    Tags and pools to track are defined in the `tagpools` configuration option.

    :param str manager_name:
        The name of the metrics publisher, this is used for the MetricManager
        publisher and all metric names will be prefixed with it.
    :param dict redis_manager:
        Connection configuration details for Redis.
    :param str count_suffix:
        Defaults to 'count'. This is the suffix appended to all
        counters. If a message is received on connector
        'foo', counters are published on
        '<manager_name>.foo.inbound.<count_suffix>'
    :param str response_time_suffix:
        Defaults to 'response_time'. This is the suffix appended to all
        average response time metrics. If a message is
        received its `message_id` is stored and when a reply for the given
        `message_id` is sent out, the timestamps are compared and a averaged
        metric is published.
    :param str session_time_suffix:
        Defaults to 'session_time'. This is the suffix appended to all session
        timer metrics. When a session starts the current time is stored under
        the `from_addr` and when the session ends, the duration of the session
        is published.
    :param str session_billing_unit:
        Defaults to ``null``. Some networks charge for sessions per unit of
        time or part there of. This means it might be useful, for example, to
        record the session duration rounded to the nearest 20 seconds. Setting
        `session_billing_unit` to a number fires an additional metric whenever
        the session duration metric is fired. The new metric records the
        duration rounded up to the next `session_billing_unit`.
    :param bool provider_metrics:
        Defaults to ``false``. Set to ``true`` to fire per-operator metrics.
    :param dict tagpools:
        A dictionary defining which tag pools and tags should be tracked.
        E.g.::

            tagpools:
                pool1:
                    track_pool: true
                    track_all_tags: true
                pool2:
                    track_tags: ["tagA"]

        This tracks `pool1` but not `pool2` and tracks all tags from `pool`
        and the tag `tagB` (from `pool2`). If this configuration
        option is missing or empty, no tag or tag pool metrics are produced.
    :param int max_lifetime:
        *DEPRECATED* This used to define how long we kept the response time
        timestamp in Redis for, but we no longer keep it in Redis.
    :param int max_session_time:
        How long to keep the session time timestamp for. Any session duration
        longer than this is not recorded. Defaults to 600 seconds.
    :param str op_mode:
        What mode to operate in, options are `passive` or `active`.
        Defaults to passive.
        *passive*:  assumes the middleware connector names are to be used as
                    the names for metrics publishing.
        *active*:   assumes that the individual messages are to be inspected
                    for their `transport_name` values.

        NOTE:   This does not apply for events or failures, the connectors
                names are always used for those since those message types are
                not guaranteed to have a `transport_name` value.
    :param list metric_connectors:
        List of connector names to fire metrics for. Useful for when wrapping
        dispatchers with many connectors, only a subset of which should
        generate metrics. Defaults to all connectors.
    """

    CONFIG_CLASS = MetricsMiddlewareConfig

    KNOWN_MODES = frozenset(['active', 'passive'])
    TAG_STRIP_RE = re.compile(r"(^[^a-zA-Z0-9_-]+)|([^a-zA-Z0-9_-]+$)")
    TAG_DOT_RE = re.compile(r"[^a-zA-Z0-9_-]+")

    def validate_config(self):
        self.manager_name = self.config.manager_name
        self.count_suffix = self.config.count_suffix
        self.response_time_suffix = self.config.response_time_suffix
        self.session_time_suffix = self.config.session_time_suffix
        self.session_billing_unit = self.config.session_billing_unit
        self.provider_metrics = self.config.provider_metrics
        self.tagpools = self.config.tagpools or {}
        for pool, cfg in self.tagpools.iteritems():
            cfg['tags'] = set(cfg.get('tags', []))
        self.max_session_time = self.config.max_session_time
        self.op_mode = self.config.op_mode
        if self.op_mode not in self.KNOWN_MODES:
            raise ConfigError('Unknown op_mode: %s' % (
                self.op_mode,))
        self.metric_connectors_specified = (
            self.config.metric_connectors is not None)
        self.metric_connectors = set(self.config.metric_connectors or [])

    @inlineCallbacks
    def setup_middleware(self):
        self.validate_config()
        self.metric_publisher = yield self.worker.start_publisher(
            MetricPublisher)
        # We don't use a VumiApi here because we don't have a Riak config for
        # it.
        self.redis = yield TxRedisManager.from_config(
            self.config.redis_manager)
        self.metric_manager = MetricManager(
            self.manager_name + '.', publisher=self.metric_publisher)
        self.metric_manager.start_polling()

    def teardown_middleware(self):
        self.metric_manager.stop_polling()
        return self.redis.close_manager()

    def get_or_create_metric(self, name, metric_class, *args, **kwargs):
        """
        Get the metric for `name`, create it with
        `metric_class(*args, **kwargs)` if it doesn't exist yet.
        """
        if name not in self.metric_manager:
            self.metric_manager.register(metric_class(name, *args, **kwargs))
        return self.metric_manager[name]

    def get_counter_metric(self, name):
        metric_name = '%s.%s' % (name, self.count_suffix)
        return self.get_or_create_metric(metric_name, Count)

    def increment_counter(self, prefix, message_type):
        metric = self.get_counter_metric('%s.%s' % (prefix, message_type))
        metric.inc()

    def get_response_time_metric(self, name):
        metric_name = '%s.%s' % (name, self.response_time_suffix)
        return self.get_or_create_metric(metric_name, TimeMetric)

    def set_response_time(self, name, time_delta):
        metric = self.get_response_time_metric(name)
        metric.set(time_delta)

    def get_session_time_metric(self, name):
        metric_name = '%s.%s' % (name, self.session_time_suffix)
        return self.get_or_create_metric(metric_name, TimeMetric)

    def set_session_time(self, name, time_delta):
        metric = self.get_session_time_metric(name)
        metric.set(time_delta)

    def key(self, transport_name, message_id):
        return '%s:%s' % (transport_name, message_id)

    def _message_metadata(self, message):
        return message['helper_metadata'].setdefault('metrics_middleware', {})

    def set_inbound_timestamp(self, transport_name, message):
        self._message_metadata(message)[transport_name] = repr(time.time())

    def get_inbound_timestamp(self, transport_name, message):
        timestamp = self._message_metadata(message).get(transport_name)
        if timestamp:
            return float(timestamp)

    def get_reply_dt(self, transport_name, message):
        timestamp = self.get_inbound_timestamp(transport_name, message)
        if timestamp:
            return time.time() - timestamp

    def set_session_start_timestamp(self, transport_name, addr):
        key = self.key(transport_name, addr)
        return self.redis.setex(
            key, self.max_session_time, repr(time.time()))

    @inlineCallbacks
    def get_session_start_timestamp(self, transport_name, addr):
        key = self.key(transport_name, addr)
        timestamp = yield self.redis.get(key)
        if timestamp:
            returnValue(float(timestamp))

    @inlineCallbacks
    def get_session_dt(self, transport_name, addr):
        timestamp = yield self.get_session_start_timestamp(
            transport_name, addr)
        if timestamp:
            returnValue(time.time() - timestamp)

    def is_metric_connector(self, connector_name):
        return (
            not self.metric_connectors_specified or
            connector_name in self.metric_connectors)

    def get_name(self, message, connector_name):
        if self.op_mode == 'active':
            return message['transport_name']
        return connector_name

    def get_provider(self, message):
        provider = message.get('provider') or 'unknown'
        return provider.lower()

    def get_tag(self, message):
        return TaggingMiddleware.map_msg_to_tag(message)

    def slugify_tagname(self, tagname):
        tagname = self.TAG_STRIP_RE.sub("", tagname)
        tagname = self.TAG_DOT_RE.sub(".", tagname)
        return tagname.lower()

    def fire_response_time(self, prefix, reply_dt):
        if reply_dt:
            self.set_response_time(prefix, reply_dt)

    def fire_session_dt(self, prefix, session_dt):
        if not session_dt:
            return
        self.set_session_time(prefix, session_dt)
        unit = self.session_billing_unit
        if unit:
            rounded_dt = math.ceil(session_dt / unit) * unit
            rounded_prefix = '%s.rounded.%ds' % (prefix, unit)
            self.set_session_time(rounded_prefix, rounded_dt)

    def fire_inbound_metrics(self, prefix, msg, session_dt):
        self.increment_counter(prefix, 'inbound')
        if msg['session_event'] == msg.SESSION_NEW:
            self.increment_counter(prefix, 'sessions_started')
        self.fire_session_dt(prefix, session_dt)

    def fire_inbound_transport_metrics(self, name, msg, session_dt):
        self.fire_inbound_metrics(name, msg, session_dt)

    def fire_inbound_provider_metrics(self, name, msg, session_dt):
        provider = self.get_provider(msg)
        self.fire_inbound_metrics(
            '%s.provider.%s' % (name, provider), msg, session_dt)

    def fire_inbound_tagpool_metrics(self, name, msg, session_dt):
        tag = self.get_tag(msg)
        if tag is None:
            return
        pool, tagname = tag
        config = self.tagpools.get(pool)
        if config is None:
            return
        if config.get('track_pool'):
            self.fire_inbound_metrics(
                '%s.tagpool.%s' % (name, pool), msg, session_dt)
        if config.get('track_all_tags') or tagname in config['tags']:
            slugname = self.slugify_tagname(tagname)
            self.fire_inbound_metrics(
                '%s.tag.%s.%s' % (name, pool, slugname), msg, session_dt)

    def fire_outbound_metrics(self, prefix, msg, session_dt):
        self.increment_counter(prefix, 'outbound')
        if msg['session_event'] == msg.SESSION_NEW:
            self.increment_counter(prefix, 'sessions_started')
        if session_dt is not None:
            self.fire_session_dt(prefix, session_dt)

    def fire_outbound_transport_metrics(self, name, msg, session_dt):
        self.fire_outbound_metrics(name, msg, session_dt)

    def fire_outbound_provider_metrics(self, name, msg, session_dt):
        provider = self.get_provider(msg)
        self.fire_outbound_metrics(
            '%s.provider.%s' % (name, provider), msg, session_dt)

    def fire_outbound_tagpool_metrics(self, name, msg, session_dt):
        tag = self.get_tag(msg)
        if tag is None:
            return
        pool, tagname = tag
        config = self.tagpools.get(pool)
        if config is None:
            return
        if config.get('track_pool'):
            self.fire_outbound_metrics(
                '%s.tagpool.%s' % (name, pool), msg, session_dt)
        if config.get('track_all_tags') or tagname in config['tags']:
            slugname = self.slugify_tagname(tagname)
            self.fire_outbound_metrics(
                '%s.tag.%s.%s' % (name, pool, slugname), msg, session_dt)

    @inlineCallbacks
    def handle_inbound(self, message, connector_name):
        if not self.is_metric_connector(connector_name):
            returnValue(message)
        name = self.get_name(message, connector_name)

        yield self.set_inbound_timestamp(name, message)
        if message['session_event'] == message.SESSION_NEW:
            yield self.set_session_start_timestamp(name, message['to_addr'])

        session_dt = None
        if message['session_event'] == message.SESSION_CLOSE:
            session_dt = yield self.get_session_dt(name, message['to_addr'])

        self.fire_inbound_transport_metrics(name, message, session_dt)
        if self.provider_metrics:
            self.fire_inbound_provider_metrics(name, message, session_dt)
        if self.tagpools:
            self.fire_inbound_tagpool_metrics(name, message, session_dt)
        returnValue(message)

    @inlineCallbacks
    def handle_outbound(self, message, connector_name):
        if not self.is_metric_connector(connector_name):
            returnValue(message)
        name = self.get_name(message, connector_name)

        if message['session_event'] == message.SESSION_NEW:
            yield self.set_session_start_timestamp(name, message['from_addr'])

        reply_dt = yield self.get_reply_dt(name, message)

        session_dt = None
        if message['session_event'] == message.SESSION_CLOSE:
            session_dt = yield self.get_session_dt(name, message['from_addr'])

        self.fire_response_time(name, reply_dt)
        self.fire_outbound_transport_metrics(name, message, session_dt)
        if self.provider_metrics:
            self.fire_outbound_provider_metrics(name, message, session_dt)
        if self.tagpools:
            self.fire_outbound_tagpool_metrics(name, message, session_dt)
        returnValue(message)

    def handle_event(self, event, connector_name):
        if not self.is_metric_connector(connector_name):
            return event
        self.increment_counter(
            connector_name, 'event.%s' % (event['event_type']))
        if event['event_type'] == 'delivery_report':
            self.increment_counter(connector_name, 'event.%s.%s' % (
                event['event_type'], event['delivery_status']))
        return event

    def handle_failure(self, failure, connector_name):
        if not self.is_metric_connector(connector_name):
            return failure
        self.increment_counter(connector_name, 'failure.%s' % (
            failure['failure_code'] or 'unspecified',))
        return failure


class ConversationMetricsMiddlewareConfig(BaseMiddleware.CONFIG_CLASS):

    redis_manager = ConfigDict(
        "Redis configuration parameters", default={}, static=True)


class ConversationMetricsMiddleware(BaseMiddleware):
    """
    Middleware that stores which conversations have received or sent messages

    :param dict redis_manager:
        Connection configuration details for Redis.
    :param dict riak_manager:
        Configuration details for Riak.
    """

    CONFIG_CLASS = ConversationMetricsMiddlewareConfig
    SUBMANAGER_PREFIX = "conversation.metrics.middleware"
    RECENT_CONV_KEY = "recent_conversations"
    OLD_RECENT_CONV_KEY = "old_recent_conversations"

    @inlineCallbacks
    def setup_middleware(self):
        # We don't use a VumiApi here because we don't have a Riak config for
        # it.
        self.redis_manager = yield TxRedisManager.from_config(
            self.config.redis_manager)
        self.redis = self.redis_manager.sub_manager(self.SUBMANAGER_PREFIX)
        self.local_recent_convs = set()
        self._looper = LoopingCall(self.update_redis_recent_convs)
        self._looper.start(1800)

    def teardown_middleware(self):
        if self._looper.running:
            self._looper.stop()
        return self.redis_manager.close_manager()

    def update_redis_recent_convs(self):
        # Note: This set will be emptied by a celery task that publishes
        # the metrics for conversations we have seen
        self.redis.sadd(self.RECENT_CONV_KEY, *self.local_recent_convs)
        self.local_recent_convs = set()

    def record_conv_seen(self, msg):
        mdh = MessageMetadataHelper(None, msg)
        conv_key = mdh.get_conversation_key()
        acc_key = mdh.get_account_key()

        # This string should be valid json. We construct it ourselves so that
        # the order is consistent, otherwise we might add duplicates to the set
        conv_details = '{"account_key": "%s","conv_key": "%s"}' % \
            (acc_key, conv_key)

        if conv_details not in self.local_recent_convs:
            self.local_recent_convs.add(conv_details)

    @inlineCallbacks
    def handle_inbound(self, message, connector_name):
        yield self.record_conv_seen(message)
        returnValue(message)

    @inlineCallbacks
    def handle_outbound(self, message, connector_name):
        yield self.record_conv_seen(message)
        returnValue(message)


class GoStoringMiddlewareConfig(StoringMiddlewareConfig):
    """
    GoStoringMiddleware configuration options.
    """

    conversation_cache_ttl = ConfigInt(
        "Time in seconds to cache conversations for.",
        default=5, static=True)


class GoStoringMiddleware(StoringMiddleware):

    CONFIG_CLASS = GoStoringMiddlewareConfig

    @inlineCallbacks
    def setup_middleware(self):
        yield super(GoStoringMiddleware, self).setup_middleware()
        self.vumi_api = yield VumiApi.from_config_async({
            "riak_manager": self.config.riak_manager,
            "redis_manager": self.config.redis_manager,
        })
        # We don't have access to our worker's conversation cache (if any), so
        # we use our own here to avoid duplicate lookups between messages for
        # the same conversation.
        self._conversation_cache = ModelObjectCache(
            reactor, self.config.conversation_cache_ttl)

    @inlineCallbacks
    def teardown_middleware(self):
        yield self._conversation_cache.cleanup()
        yield self.vumi_api.close()
        yield super(GoStoringMiddleware, self).teardown_middleware()

    def get_batch_id(self, msg):
        raise NotImplementedError("Sub-classes should implement .get_batch_id")

    @inlineCallbacks
    def handle_inbound(self, message, connector_name):
        batch_id = yield self.get_batch_id(message)
        yield self.store.add_inbound_message(message, batch_ids=[batch_id])
        returnValue(message)

    @inlineCallbacks
    def handle_outbound(self, message, connector_name):
        batch_id = yield self.get_batch_id(message)
        yield self.store.add_outbound_message(message, batch_ids=[batch_id])
        returnValue(message)


class ConversationStoringMiddleware(GoStoringMiddleware):
    @inlineCallbacks
    def get_batch_id(self, msg):
        mdh = MessageMetadataHelper(
            self.vumi_api, msg, conversation_cache=self._conversation_cache)
        conversation = yield mdh.get_conversation()
        returnValue(conversation.batch.key)


class RouterStoringMiddleware(GoStoringMiddleware):
    @inlineCallbacks
    def get_batch_id(self, msg):
        mdh = MessageMetadataHelper(
            self.vumi_api, msg, conversation_cache=self._conversation_cache)
        router = yield mdh.get_router()
        returnValue(router.batch.key)
