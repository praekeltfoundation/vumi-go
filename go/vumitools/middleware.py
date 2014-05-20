# -*- test-case-name: go.vumitools.tests.test_middleware -*-
import time

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.middleware.base import TransportMiddleware, BaseMiddleware
from vumi.middleware.message_storing import StoringMiddleware
from vumi.utils import normalize_msisdn
from vumi.blinkenlights.metrics import (
    MetricPublisher, Count, Metric, MetricManager)
from vumi.errors import ConfigError
from vumi.persist.txredis_manager import TxRedisManager

from go.vumitools.api import VumiApi
from go.vumitools.utils import MessageMetadataHelper


class NormalizeMsisdnMiddleware(TransportMiddleware):

    def setup_middleware(self):
        self.country_code = self.config['country_code']
        self.strip_plus = self.config.get('strip_plus', False)

    def handle_inbound(self, message, endpoint):
        from_addr = normalize_msisdn(message.get('from_addr'),
                                     country_code=self.country_code)
        message['from_addr'] = from_addr
        return message

    def handle_outbound(self, message, endpoint):
        to_addr = normalize_msisdn(message.get('to_addr'),
                                   country_code=self.country_code)
        if self.strip_plus:
            to_addr = to_addr.lstrip('+')
        message['to_addr'] = to_addr
        return message


class OptOutMiddleware(BaseMiddleware):

    @inlineCallbacks
    def setup_middleware(self):
        self.vumi_api = yield VumiApi.from_config_async(self.config)

        self.case_sensitive = self.config.get('case_sensitive', False)
        keywords = self.config.get('optout_keywords', [])
        self.optout_keywords = set([self.casing(word) for word in keywords])

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


class MetricsMiddleware(BaseMiddleware):
    """
    Middleware that publishes metrics on messages flowing through.
    It tracks the number of messages sent & received on the various
    transports and the average response times for messages received.

    :param str manager_name:
        The name of the metrics publisher, this is used for the MetricManager
        publisher and all metric names will be prefixed with it.
    :param str count_suffix:
        Defaults to 'count'. This is the suffix appended to all
        `transport_name` based counters. If a message is received on endpoint
        'foo', counters are published on
        '<manager_name>.foo.inbound.<count_suffix>'
    :param str response_time_suffix:
        Defaults to 'response_time'. This is the suffix appended to all
        `transport_name` based average response time metrics. If a message is
        received its `message_id` is stored and when a reply for the given
        `message_id` is sent out, the timestamps are compared and a averaged
        metric is published.
    :param int max_lifetime:
        How long to keep a timestamp for. Anything older than this is trashed.
        Defaults to 60 seconds.
    :param dict redis_manager:
        Connection configuration details for Redis.
    :param str op_mode:
        What mode to operate in, options are `passive` or `active`.
        Defaults to passive.
        *passive*:  assumes the middleware endpoints are to be used as the
                    names for metrics publishing.
        *active*:   assumes that the individual messages are to be inspected
                    for their `transport_name` values.

        NOTE:   This does not apply for events or failures, the endpoints
                are always used for those since those message types are not
                guaranteed to have a `transport_name` value.
    """

    KNOWN_MODES = frozenset(['active', 'passive'])

    def validate_config(self):
        self.manager_name = self.config['manager_name']
        self.count_suffix = self.config.get('count_suffix', 'count')
        self.response_time_suffix = self.config.get('response_time_suffix',
            'response_time')
        self.max_lifetime = int(self.config.get('max_lifetime', 60))
        self.op_mode = self.config.get('op_mode', 'passive')
        if self.op_mode not in self.KNOWN_MODES:
            raise ConfigError('Unknown op_mode: %s' % (
                self.op_mode,))

    @inlineCallbacks
    def setup_middleware(self):
        self.validate_config()
        self.metric_publisher = yield self.worker.start_publisher(
            MetricPublisher)
        # We don't use a VumiApi here because we don't have a Riak config for
        # it.
        self.redis = yield TxRedisManager.from_config(
            self.config['redis_manager'])
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

    def increment_counter(self, transport_name, message_type):
        metric = self.get_counter_metric('%s.%s' % (transport_name,
            message_type))
        metric.inc()

    def get_response_time_metric(self, name):
        metric_name = '%s.%s' % (name, self.response_time_suffix)
        return self.get_or_create_metric(metric_name, Metric)

    def set_response_time(self, transport_name, time):
        metric = self.get_response_time_metric(transport_name)
        metric.set(time)

    def key(self, transport_name, message_id):
        return '%s:%s' % (transport_name, message_id)

    def set_inbound_timestamp(self, transport_name, message):
        key = self.key(transport_name, message['message_id'])
        return self.redis.setex(
            key, self.max_lifetime, repr(time.time()))

    @inlineCallbacks
    def get_outbound_timestamp(self, transport_name, message):
        key = self.key(transport_name, message['in_reply_to'])
        timestamp = yield self.redis.get(key)
        if timestamp:
            returnValue(float(timestamp))

    @inlineCallbacks
    def compare_timestamps(self, transport_name, message):
        timestamp = yield self.get_outbound_timestamp(transport_name, message)
        if timestamp:
            self.set_response_time(transport_name, time.time() - timestamp)

    def get_name(self, message, endpoint):
        if self.op_mode == 'active':
            return message['transport_name']
        return endpoint

    @inlineCallbacks
    def handle_inbound(self, message, endpoint):
        name = self.get_name(message, endpoint)
        self.increment_counter(name, 'inbound')
        yield self.set_inbound_timestamp(name, message)
        returnValue(message)

    @inlineCallbacks
    def handle_outbound(self, message, endpoint):
        name = self.get_name(message, endpoint)
        self.increment_counter(name, 'outbound')
        yield self.compare_timestamps(name, message)
        returnValue(message)

    def handle_event(self, event, endpoint):
        self.increment_counter(endpoint, 'event.%s' % (event['event_type']))
        if event['event_type'] == 'delivery_report':
            self.increment_counter(endpoint, 'event.%s.%s' % (
                event['event_type'], event['delivery_status']))
        return event

    def handle_failure(self, failure, endpoint):
        self.increment_counter(endpoint, 'failure.%s' % (
            failure['failure_code'] or 'unspecified',))
        return failure


class GoStoringMiddleware(StoringMiddleware):
    @inlineCallbacks
    def setup_middleware(self):
        yield super(GoStoringMiddleware, self).setup_middleware()
        self.vumi_api = yield VumiApi.from_config_async(self.config)

    @inlineCallbacks
    def teardown_middleware(self):
        yield self.vumi_api.redis.close_manager()
        yield super(GoStoringMiddleware, self).teardown_middleware()

    def get_batch_id(self, msg):
        raise NotImplementedError("Sub-classes should implement .get_batch_id")

    @inlineCallbacks
    def handle_inbound(self, message, connector_name):
        batch_id = yield self.get_batch_id(message)
        yield self.store.add_inbound_message(message, batch_id=batch_id)
        returnValue(message)

    @inlineCallbacks
    def handle_outbound(self, message, connector_name):
        batch_id = yield self.get_batch_id(message)
        yield self.store.add_outbound_message(message, batch_id=batch_id)
        returnValue(message)


class ConversationStoringMiddleware(GoStoringMiddleware):
    @inlineCallbacks
    def get_batch_id(self, msg):
        mdh = MessageMetadataHelper(self.vumi_api, msg)
        conversation = yield mdh.get_conversation()
        returnValue(conversation.batch.key)


class RouterStoringMiddleware(GoStoringMiddleware):
    @inlineCallbacks
    def get_batch_id(self, msg):
        mdh = MessageMetadataHelper(self.vumi_api, msg)
        router = yield mdh.get_router()
        returnValue(router.batch.key)
