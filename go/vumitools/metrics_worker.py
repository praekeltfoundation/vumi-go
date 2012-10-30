# -*- test-case-name: go.vumitools.tests.test_metrics_worker -*-

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall

from vumi import log
from vumi.service import Worker

from go.vumitools.api import VumiApi, VumiApiCommand


class GoMetricsWorker(Worker):
    """A metrics collection worker for Go applications.

    This worker operates by finding all conversations that require metrics
    collection and sending commands to the relevant application workers to
    trigger the actual metrics.

    """

    worker_name = 'go_metrics'

    @inlineCallbacks
    def startWorker(self):
        self.validate_config()

        self.vumi_api = yield VumiApi.from_config_async(self.config)
        self.redis = self.vumi_api.redis

        self.command_publisher = yield self.publish_to(
            self.api_routing_config['routing_key'])

        self._looper = LoopingCall(self.metrics_loop_func)
        self._looper.start(self.metrics_interval)

    def stopWorker(self):
        if self._looper.running:
            self._looper.stop()
        return self.redis.close_manager()

    def validate_config(self):
        self.metrics_interval = int(self.config.get('metrics_interval', 300))
        self.api_routing_config = VumiApiCommand.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))

    @inlineCallbacks
    def metrics_loop_func(self):
        account_keys = yield self.find_account_keys()
        conversations = []
        # We deliberarely serialise this. We don't want to hit the datastore
        # too hard for metrics.
        for account_key in account_keys:
            convs = yield self.find_conversations_for_account(account_key)
            conversations.extend(convs)
        log.info(
            "Processing metrics for %s conversations owned by %s users." % (
                len(conversations), len(account_keys)))
        for conversation in conversations:
            yield self.send_metrics_command(conversation)

    def find_account_keys(self):
        return self.redis.smembers('metrics_accounts')

    def find_conversations_for_account(self, account_key):
        user_api = self.vumi_api.get_user_api(account_key)
        return user_api.running_conversations()

    def send_metrics_command(self, conversation):
        cmd = VumiApiCommand.command(
            conversation.conversation_type, 'collect_metrics',
            conversation_key=conversation.key,
            user_account_key=conversation.user_account.key)
        return self.command_publisher.publish_message(cmd)
