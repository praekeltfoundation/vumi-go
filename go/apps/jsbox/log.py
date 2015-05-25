# -*- test-case-name: go.apps.jsbox.tests.test_log -*-
# -*- coding: utf-8 -*-

import logging
import datetime

from twisted.internet.defer import inlineCallbacks, returnValue

from vxsandbox import LoggingResource

from vumi import log
from vumi.persist.redis_base import Manager
from vumi.persist.txredis_manager import TxRedisManager


class LogManager(object):
    """
    Store and retrieves logs for a jsbox application.
    """

    # this uses Manager.calls_manager so that it can be used from
    # Django.

    DEFAULT_MAX_LOGS_PER_CONVERSATION = 1000
    DEFAULT_SUB_STORE = "jsbox_logs_store"

    def __init__(self, redis, max_logs_per_conversation=None,
                 sub_store=DEFAULT_SUB_STORE):
        if sub_store is not None:
            redis = redis.sub_manager(sub_store)
        self.redis = self.manager = redis
        if max_logs_per_conversation is None:
            max_logs_per_conversation = self.DEFAULT_MAX_LOGS_PER_CONVERSATION
        self.max_logs_per_conversation = max_logs_per_conversation

    def _conv_key(self, campaign_key, conversation_key):
        return ":".join([campaign_key, conversation_key])

    @Manager.calls_manager
    def add_log(self, campaign_key, conversation_key, msg, level):
        ts = datetime.datetime.utcnow().isoformat()
        full_msg = "[%s, %s] %s" % (ts, logging.getLevelName(level), msg)
        conv_key = self._conv_key(campaign_key, conversation_key)
        yield self.redis.lpush(conv_key, full_msg)
        yield self.redis.ltrim(conv_key, 0, self.max_logs_per_conversation - 1)

    @Manager.calls_manager
    def get_logs(self, campaign_key, conversation_key):
        conv_key = self._conv_key(campaign_key, conversation_key)
        msgs = yield self.redis.lrange(conv_key, 0, -1)
        returnValue(msgs)


class GoLoggingResource(LoggingResource):
    """
    Resource that allows a sandbox to log messages.

    Messages are logged both via Twisted's logging framework and
    to a per-conversation log store in Redis.
    """

    @inlineCallbacks
    def setup(self):
        super(GoLoggingResource, self).setup()
        redis_config = self.config.get('redis_manager', {})
        max_logs_per_conversation = self.config.get(
            'max_logs_per_conversation')
        self._redis = yield TxRedisManager.from_config(redis_config)
        self.log_manager = LogManager(
            self._redis, max_logs_per_conversation=max_logs_per_conversation)

    @inlineCallbacks
    def teardown(self):
        yield self._redis.close_manager()
        yield super(GoLoggingResource, self).teardown()

    @inlineCallbacks
    def log(self, api, msg, level):
        conv = self.app_worker.conversation_for_api(api)
        campaign_key = conv.user_account.key
        conversation_key = conv.key

        # The keys may be unicode, so make everything unicode and then encode.
        internal_msg = u"[Account: %s, Conversation: %s] %r" % (
            campaign_key, conversation_key, msg)
        log.msg(internal_msg.encode("ascii"), logLevel=level)

        yield self.log_manager.add_log(campaign_key, conversation_key,
                                       msg, level)
