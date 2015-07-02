# -*- test-case-name: go.vumitools.tests.test_metrics_worker -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall

from vumi import log
from vumi.worker import BaseWorker
from vumi.config import ConfigInt, ConfigError
from vumi.persist.model import Manager

from go.vumitools.api import VumiApiCommand, ApiCommandPublisher
from go.vumitools.app_worker import GoWorkerConfigMixin, GoWorkerMixin


class GoMetricsWorkerConfig(BaseWorker.CONFIG_CLASS, GoWorkerConfigMixin):
    """At the start of each `metrics_interval` the :class:`GoMetricsWorker`
       collects a list of all active conversations and distributes them
       into `metrics_interval / metrics_granularity` buckets.

       Immediately afterwards and then after each `metrics_granulatiry`
       interval, the metrics worker sends a `collect_metrics` command to each
       of the conversations in the current bucket until all buckets have been
       processed.

       Once all buckets have been processed, active conversations are
       collected again and the cycle repeats.
       """

    metrics_interval = ConfigInt(
        "How often (in seconds) the worker should send `collect_metrics` "
        "commands for each conversation. Must be an integer multiple of "
        "`metrics_granularity`.",
        default=300,
        static=True)

    metrics_granularity = ConfigInt(
        "How often (in seconds) the worker should process a bucket of "
        "conversations.",
        default=5,
        static=True)

    def post_validate(self):
        if (self.metrics_interval % self.metrics_granularity != 0):
            raise ConfigError("Metrics interval must be an integer multiple"
                              " of metrics granularity.")


class GoMetricsWorker(BaseWorker, GoWorkerMixin):
    """A metrics collection worker for Go applications.

    This worker operates by finding all conversations that require metrics
    collection and sending commands to the relevant application workers to
    trigger the actual metrics.

    """

    CONFIG_CLASS = GoMetricsWorkerConfig
    worker_name = 'go_metrics'

    @inlineCallbacks
    def setup_worker(self):
        yield self._go_setup_worker()
        config = self.get_static_config()

        self.command_publisher = yield self.start_publisher(
            ApiCommandPublisher)

        self._current_bucket = 0
        self._num_buckets = (
            config.metrics_interval // config.metrics_granularity)
        self._buckets = dict((i, []) for i in range(self._num_buckets))
        self._conversation_workers = {}

        self._looper = LoopingCall(self.metrics_loop_func)
        self._looper.start(config.metrics_granularity)

    @inlineCallbacks
    def teardown_worker(self):
        if self._looper.running:
            self._looper.stop()
        yield self._go_teardown_worker()

    def bucket_for_conversation(self, conv_key):
        return hash(conv_key) % self._num_buckets

    @inlineCallbacks
    def populate_conversation_buckets(self):
        account_keys = yield self.find_account_keys()
        num_conversations = 0
        # We deliberarely serialise this. We don't want to hit the datastore
        # too hard for metrics.
        for account_key in account_keys:
            conv_keys = yield self.find_conversations_for_account(account_key)
            num_conversations += len(conv_keys)
            for conv_key in conv_keys:
                bucket = self.bucket_for_conversation(conv_key)
                if conv_key not in self._conversation_workers:
                    # TODO: Clear out archived conversations
                    user_api = self.vumi_api.get_user_api(account_key)
                    conv = yield user_api.get_wrapped_conversation(conv_key)
                    self._conversation_workers[conv_key] = conv.worker_name
                worker_name = self._conversation_workers[conv_key]
                self._buckets[bucket].append(
                    (account_key, conv_key, worker_name))
        log.info(
            "Scheduled metrics commands for %d conversations in %d accounts."
            % (num_conversations, len(account_keys)))

    @inlineCallbacks
    def process_bucket(self, bucket):
        convs, self._buckets[bucket] = self._buckets[bucket], []
        for account_key, conversation_key, worker_name in convs:
            yield self.send_metrics_command(
                account_key, conversation_key, worker_name)

    def increment_bucket(self):
        self._current_bucket += 1
        self._current_bucket %= self._num_buckets

    @inlineCallbacks
    def metrics_loop_func(self):
        if self._current_bucket == 0:
            yield self.populate_conversation_buckets()
        yield self.process_bucket(self._current_bucket)
        self.increment_bucket()

    def setup_connectors(self):
        pass

    @Manager.calls_manager
    def find_account_keys(self):
        keys = yield self.vumi_api.account_store.users.all_keys()
        disabled_keys = yield self.redis.smembers('disabled_metrics_accounts')
        returnValue(set(keys) - set(disabled_keys))

    def find_conversations_for_account(self, account_key):
        user_api = self.vumi_api.get_user_api(account_key)
        return user_api.conversation_store.list_running_conversations()

    def send_metrics_command(self, account_key, conversation_key, worker_name):
        cmd = VumiApiCommand.command(
            worker_name,
            'collect_metrics',
            conversation_key=conversation_key,
            user_account_key=account_key)
        return self.command_publisher.publish_message(cmd)
