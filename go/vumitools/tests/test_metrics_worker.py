"""Tests for go.vumitools.metrics_worker."""

import copy
import re

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import Clock, LoopingCall

from go.vumitools.tests.utils import GoWorkerTestCase
from go.vumitools import metrics_worker


class GoMetricsWorkerTestCase(GoWorkerTestCase):
    worker_class = metrics_worker.GoMetricsWorker

    def setUp(self):
        super(GoMetricsWorkerTestCase, self).setUp()
        self.clock = Clock()
        self.patch(metrics_worker, 'LoopingCall', self.looping_call)

    def get_metrics_worker(self, config=None, start=True,
                           needs_looping=False, needs_hash=False):
        if not needs_looping:
            self.patch(metrics_worker, 'LoopingCall', self.no_looping)
        if not needs_hash:
            self.patch(metrics_worker.GoMetricsWorker,
                       'bucket_for_conversation',
                       self.dummy_bucket_for_conversation)
        if config is None:
            config = {}
        return self.get_worker(self.mk_config(config), start)

    def rkey(self, name):
        return name

    def looping_call(self, *args, **kwargs):
        looping_call = LoopingCall(*args, **kwargs)
        looping_call.clock = self.clock
        return looping_call

    def no_looping(self, *args, **kw):
        return self.looping_call(lambda: None)

    def dummy_bucket_for_conversation(self, conv):
        digits = re.sub('[^0-9]', '', conv.name) or '0'
        return int(digits) % 60

    def make_account(self, worker, username):
        return self.mk_user(worker.vumi_api, username)

    def make_conv(self, user_api, conv_name, conv_type=u'my_conv'):
        return user_api.new_conversation(conv_type, conv_name, u'', {})

    def start_conv(self, conv):
        conv.set_status_started()
        return conv.save()

    def archive_conv(self, conv):
        conv.set_status_stopped()
        conv.set_status_finished()
        return conv.save()

    @inlineCallbacks
    def make_accounts_and_conversations(self, worker, **account_definitions):
        accounts, conversations = {}, {}
        for username, convs in account_definitions.iteritems():
            account = yield self.make_account(worker, unicode(username))
            accounts[username] = account
            user_api = worker.vumi_api.get_user_api(account.key)
            for conv_name in convs:
                conv = yield self.make_conv(user_api, unicode(conv_name))
                conversations[conv_name] = conv

        returnValue((accounts, conversations))

    @inlineCallbacks
    def test_bucket_for_conversation(self):
        worker = yield self.get_metrics_worker(needs_hash=True)
        accounts, conversations = yield self.make_accounts_and_conversations(
            worker, acc1=["conv1"])
        bucket = worker.bucket_for_conversation(conversations["conv1"])
        self.assertEqual(bucket, hash(conversations["conv1"].key) % 60)

    def assert_conversations_bucketed(self, worker, expected):
        expected = copy.deepcopy(expected)
        buckets = copy.deepcopy(worker._buckets)
        for key in range(60):
            buckets[key] = sorted(c.key for c in buckets[key])
            expected[key] = sorted(c.key for c in expected.get(key, []))
            if buckets[key] == expected[key]:
                del buckets[key]
                del expected[key]
        self.assertEqual(buckets, expected)

    @inlineCallbacks
    def test_populate_conversation_buckets(self):
        worker = yield self.get_metrics_worker()

        accounts, conversations = yield self.make_accounts_and_conversations(
            worker, acc1=["conv1", "conv2a", "conv2b", "conv4"])
        for conv in conversations.values():
            self.start_conv(conv)

        self.assert_conversations_bucketed(worker, {})
        yield worker.populate_conversation_buckets()
        self.assert_conversations_bucketed(worker, {
            1: [conversations["conv1"]],
            2: [conversations["conv2a"], conversations["conv2b"]],
            4: [conversations["conv4"]],
        })

    @inlineCallbacks
    def test_process_bucket(self):
        worker = yield self.get_metrics_worker()

        accounts, conversations = yield self.make_accounts_and_conversations(
            worker, acc1=["conv1", "conv2a", "conv2b", "conv4"])
        for conv in conversations.values():
            self.start_conv(conv)

        self.assert_conversations_bucketed(worker, {})
        yield worker.populate_conversation_buckets()
        yield worker.process_bucket(2)
        self.assert_conversations_bucketed(worker, {
            1: [conversations["conv1"]],
            4: [conversations["conv4"]],
        })

    @inlineCallbacks
    def test_increment_bucket(self):
        worker = yield self.get_metrics_worker()
        self.assertEqual(worker._current_bucket, 0)
        worker.increment_bucket()
        self.assertEqual(worker._current_bucket, 1)
        worker._current_bucket = 59
        worker.increment_bucket()
        self.assertEqual(worker._current_bucket, 0)

    @inlineCallbacks
    def test_metrics_poller(self):
        polls = []
        # Replace metrics worker with one that hasn't started yet.
        worker = yield self.get_metrics_worker(start=False, needs_looping=True)
        worker.metrics_loop_func = lambda: polls.append(None)
        self.assertEqual(0, len(polls))
        # Start worker.
        yield worker.startWorker()
        self.assertEqual(1, len(polls))
        # Pass time, but not enough to trigger a metric run.
        self.clock.advance(4)
        self.assertEqual(1, len(polls))
        # Pass time, trigger a metric run.
        self.clock.advance(1)
        self.assertEqual(2, len(polls))

    @inlineCallbacks
    def test_find_accounts(self):
        worker = yield self.get_metrics_worker()
        accounts, conversations = yield self.make_accounts_and_conversations(
            worker, acc1=[], acc2=[], acc3=[])
        yield worker.redis.sadd('disabled_metrics_accounts',
                                accounts["acc3"].key)

        account_keys = yield worker.find_account_keys()
        self.assertEqual(
            sorted([accounts["acc1"].key, accounts["acc2"].key]),
            sorted(account_keys))

    @inlineCallbacks
    def test_find_conversations_for_account(self):
        worker = yield self.get_metrics_worker()
        accounts, conversations = yield self.make_accounts_and_conversations(
            worker, acc1=["conv1", "conv2", "conv3"])

        yield self.archive_conv(conversations["conv1"])
        yield self.start_conv(conversations["conv2"])

        active_conversations = yield worker.find_conversations_for_account(
            accounts["acc1"].key)
        self.assertEqual([c.key for c in active_conversations],
                         [conversations["conv2"].key])

    @inlineCallbacks
    def test_send_metrics_command(self):
        worker = yield self.get_metrics_worker()
        accounts, conversations = yield self.make_accounts_and_conversations(
            worker, acc1=["conv1"])

        yield self.start_conv(conversations["conv1"])
        yield worker.send_metrics_command(conversations["conv1"])
        [cmd] = self._get_dispatched('vumi.api')

        self.assertEqual(cmd['worker_name'], 'my_conv_application')
        self.assertEqual(cmd.payload['kwargs']['conversation_key'],
                         conversations["conv1"].key)
        self.assertEqual(cmd.payload['kwargs']['user_account_key'],
                         accounts["acc1"].key)

    @inlineCallbacks
    def setup_metric_loop_conversations(self, worker):
        accounts, conversations = yield self.make_accounts_and_conversations(
            worker, acc1=["conv0", "conv1"], acc2=["conv2", "conv3"])

        yield self.start_conv(conversations["conv0"])
        yield self.start_conv(conversations["conv1"])
        yield self.start_conv(conversations["conv2"])
        yield self.start_conv(conversations["conv3"])

        returnValue(conversations)

    @inlineCallbacks
    def test_metrics_loop_func_bucket_zero(self):
        worker = yield self.get_metrics_worker()
        conversations = yield self.setup_metric_loop_conversations(worker)

        self.assertEqual(worker._current_bucket, 0)
        yield worker.metrics_loop_func()
        self.assertEqual(worker._current_bucket, 1)

        cmds = self._get_dispatched('vumi.api')
        conv_keys = [c.payload['kwargs']['conversation_key'] for c in cmds]
        self.assertEqual(conv_keys, [conversations["conv0"].key])

        self.assert_conversations_bucketed(worker, {
            1: [conversations["conv1"]],
            2: [conversations["conv2"]],
            3: [conversations["conv3"]],
        })

    @inlineCallbacks
    def test_metrics_loop_func_bucket_nonzero(self):
        worker = yield self.get_metrics_worker()
        conversations = yield self.setup_metric_loop_conversations(worker)
        yield worker.populate_conversation_buckets()

        worker._current_bucket = 1
        yield worker.metrics_loop_func()
        self.assertEqual(worker._current_bucket, 2)

        cmds = self._get_dispatched('vumi.api')
        conv_keys = [c.payload['kwargs']['conversation_key'] for c in cmds]
        self.assertEqual(conv_keys, [conversations["conv1"].key])

        self.assert_conversations_bucketed(worker, {
            0: [conversations["conv0"]],
            2: [conversations["conv2"]],
            3: [conversations["conv3"]],
        })
