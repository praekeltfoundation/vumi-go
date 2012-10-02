# -*- test-case-name: go.vumitools.tests.test_middleware -*-
import sys
import time

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.middleware.tagger import TaggingMiddleware
from vumi.middleware.base import TransportMiddleware, BaseMiddleware
from vumi.utils import normalize_msisdn
from vumi.components.tagpool import TagpoolManager
from vumi.blinkenlights.metrics import MetricManager, Count, Metric
from vumi.persist.txredis_manager import TxRedisManager
from vumi.errors import ConfigError

from go.vumitools.credit import CreditManager


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
        if self.strip_plus:
            message['to_addr'] = message['to_addr'].lstrip('+')
        return message


class DebitAccountError(Exception):
    """Exception raised if a message can't be paid for."""


class NoUserError(DebitAccountError):
    """Account could not be debited because no user was found."""


class NoTagError(DebitAccountError):
    """Account could not be debited because no tag was found."""


class BadTagPool(DebitAccountError):
    """Account could not be debited because the tag pool doesn't
       specify a cost."""


class InsufficientCredit(DebitAccountError):
    """Account could not be debited because the user account has
       insufficient credit."""


class OptOutMiddleware(BaseMiddleware):

    def setup_middleware(self):
        self.case_sensitive = self.config.get('case_sensitive', False)
        keywords = self.config.get('optout_keywords', [])
        self.optout_keywords = set([self.casing(word)
                                        for word in keywords])

    def casing(self, word):
        if not self.case_sensitive:
            return word.lower()
        return word

    def handle_inbound(self, message, endpoint):
        keyword = (message['content'] or '').strip()
        helper_metadata = message['helper_metadata']
        optout_metadata = helper_metadata.setdefault('optout', {})
        if self.casing(keyword) in self.optout_keywords:
            optout_metadata['optout'] = True
            optout_metadata['optout_keyword'] = self.casing(keyword)
        else:
            optout_metadata['optout'] = False
        return message

    @staticmethod
    def is_optout_message(message):
        return message['helper_metadata'].get('optout', {}).get('optout')


class DebitAccountMiddleware(TransportMiddleware):

    def setup_middleware(self):
        # TODO: There really needs to be a helper function to
        #       turn this config into managers.
        from go.vumitools.api import get_redis
        r_server = get_redis(self.config)
        tpm_config = self.config.get('tagpool_manager', {})
        tpm_prefix = tpm_config.get('tagpool_prefix', 'tagpool_store')
        self.tpm = TagpoolManager(r_server, tpm_prefix)
        cm_config = self.config.get('credit_manager', {})
        cm_prefix = cm_config.get('credit_prefix', 'credit_store')
        self.cm = CreditManager(r_server, cm_prefix)

    def _credits_per_message(self, pool):
        tagpool_metadata = self.tpm.get_metadata(pool)
        credits_per_message = tagpool_metadata.get('credits_per_message')
        try:
            credits_per_message = int(credits_per_message)
            assert credits_per_message >= 0
        except Exception:
            exc_tb = sys.exc_info()[2]
            raise (BadTagPool,
                   BadTagPool("Invalid credits_per_message for pool %r"
                              % (pool,)),
                   exc_tb)
        return credits_per_message

    @staticmethod
    def map_msg_to_user(msg):
        """Convenience method for retrieving a user that was added
        to a message.
        """
        user_account = msg['helper_metadata'].get('go', {}).get('user_account')
        return user_account

    @staticmethod
    def map_payload_to_user(payload):
        """Convenience method for retrieving a user from a payload."""
        go_metadata = payload.get('helper_metadata', {}).get('go', {})
        return go_metadata.get('user_account')

    @staticmethod
    def add_user_to_message(msg, user_account_key):
        """Convenience method for adding a user to a message."""
        go_metadata = msg['helper_metadata'].setdefault('go', {})
        go_metadata['user_account'] = user_account_key

    @staticmethod
    def add_user_to_payload(payload, user_account_key):
        """Convenience method for adding a user to a message payload."""
        helper_metadata = payload.setdefault('helper_metadata', {})
        go_metadata = helper_metadata.setdefault('go', {})
        go_metadata['user_account'] = user_account_key

    def handle_outbound(self, msg, endpoint):
        # TODO: what actually happens when we raise an exception from
        #       inside middleware?
        user_account_key = self.map_msg_to_user(msg)
        if user_account_key is None:
            raise NoUserError(msg)
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        if tag is None:
            raise NoTagError(msg)
        credits_per_message = self._credits_per_message(tag[0])
        self._debit_account(user_account_key, credits_per_message)
        success = self.cm.debit(user_account_key, credits_per_message)
        if not success:
            raise InsufficientCredit("User %r has insufficient credit"
                                     " to debit %r." %
                                     (user_account_key, credits_per_message))
        return msg

class MetricsMiddleware(BaseMiddleware):
    """
    Middleware that publishes metrics on messages flowing through.
    It tracks the number of messages sent & received on the various
    transports and the average response times for messages received.

    :param str manager_name:
        The name of the metrics publisher, this is used for the MetricManager
        publisher and all metric names will be prefixed with it.
    :param str count_suffix:
        Defaults to 'count'. This is the suffix appended to all `transport_name`
        based counters. If a message is received on endpoint 'foo', counters
        are published on '<manager_name>.foo.inbound.<count_suffix>'
    :param str response_time_suffix:
        Defaults to 'response_time'. This is the suffix appended to all
        `transport_name` based average response time metrics. If a message is
        received its `message_id` is stored and when a reply for the given
        `message_id` is sent out, the timestamps are compared and a averaged
        metric is published.
    :param dict redis_manager:
        Connection configuration details for Redis.
    :param str op_mode:
        What mode to operate in, options are `passive` or `active`.
        Defaults to passive.
        *passive*:  assumes the middleware endpoints are to be used as the names
                    for metrics publishing.
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
        self.op_mode = self.config.get('op_mode', 'passive')
        if self.op_mode not in self.KNOWN_MODES:
            raise ConfigError('Unknown op_mode: %s' % (
                self.op_mode,))

    @inlineCallbacks
    def setup_middleware(self):
        self.validate_config()
        self.redis = yield TxRedisManager.from_config(
            self.config['redis_manager'])
        self.metric_manager = yield self.worker.start_publisher(MetricManager,
            "%s." % (self.manager_name,))

    def teardown_middleware(self):
        self.metric_manager.stop()

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
        return self.redis.set(key, repr(time.time()))

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
