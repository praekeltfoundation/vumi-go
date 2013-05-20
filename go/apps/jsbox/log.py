# -*- test-case-name: go.apps.jsbox.tests.test_log -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.application.sandbox import LoggingResource
from vumi.persist.redis_base import Manager
from vumi.persist.txredis_manager import TxRedisManager


class LogManager(object):
    """
    Store and retrieves logs for a jsbox application.
    """

    # this uses Manager.calls_manager so that it can be used from
    # Django.

    DEFAULT_MAX_LOGS_PER_CONVERSATION = 1000

    def __init__(self, redis, max_logs_per_conversation=None):
        self.redis = self.manager = redis
        if max_logs_per_conversation is None:
            max_logs_per_conversation = self.DEFAULT_MAX_LOGS_PER_CONVERSATION
        self.max_logs_per_conversation = max_logs_per_conversation

    def _conv_key(self, campaign_key, conversation_key):
        return ":".join([campaign_key, conversation_key])

    @Manager.calls_manager
    def add_log(self, campaign_key, conversation_key, msg):
        conv_key = self._conv_key(campaign_key, conversation_key)
        yield self.redis.lpush(conv_key, msg)
        yield self.redis.ltrim(conv_key, self.max_logs_per_conversation - 1)

    @Manager.calls_manaager
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
        redis_config = self.config.get('redis_manager', {})
        max_logs_per_conversation = self.config.get(
            'max_logs_per_conversation')
        redis = yield TxRedisManager.from_config(redis_config)
        self.log_manager = LogManager(redis, max_logs_per_conversation)

    @inlineCallbacks
    def handle_info(self, api, command):
        """
        Logs a message at the INFO level.

        Command fields:
            - ``msg``: the message to log.

        Success reply fields:
            - ``success``: set to ``true``

        Example:
        .. code-block:: javascript
            api.request(
                'log.info',
                {msg: 'Logging this message.'},
                function(reply) {
                    // reply.success is true here
                });
        """
        if 'msg' not in command:
            returnValue(self.reply(command, success=False,
                                   reason="Logging expects a value for msg."))
        msg = str(command['msg'])
        log.info(msg)

        conv = self.app_worker.conversation_for_api(api)
        campaign_key = conv.user_account_key
        conversation_key = conv.key

        yield self.log_manager.add_log(campaign_key, conversation_key, msg)
        returnValue(self.reply(command, success=True))
