"""Tests for go.vumitools.metrics_worker."""

import copy
import re

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import Clock, LoopingCall

from vumi.tests.helpers import VumiTestCase

from go.vumitools import metrics_worker
from go.vumitools.tests.helpers import VumiApiHelper

from vumi.tests.utils import LogCatcher


class TestGoMetricsWorker(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.clock = Clock()
        self.patch(metrics_worker, 'LoopingCall', self.looping_call)
        self.conversation_names = {}

    def get_metrics_worker(self, config=None, start=True,
                           needs_looping=False, needs_hash=False):
        if not needs_looping:
            self.patch(metrics_worker, 'LoopingCall', self.no_looping)
        if not needs_hash:
            self.patch(metrics_worker.GoMetricsWorker,
                       'bucket_for_conversation',
                       self.dummy_bucket_for_conversation)
        config = self.vumi_helper.mk_config(config or {})
        return self.vumi_helper.get_worker_helper().get_worker(
            metrics_worker.GoMetricsWorker, config, start=start)

    def rkey(self, name):
        return name

    def looping_call(self, *args, **kwargs):
        looping_call = LoopingCall(*args, **kwargs)
        looping_call.clock = self.clock
        return looping_call

    def no_looping(self, *args, **kw):
        return self.looping_call(lambda: None)

    def dummy_bucket_for_conversation(self, conv_key):
        conv_name = self.conversation_names[conv_key]
        digits = re.sub('[^0-9]', '', conv_name) or '0'
        return int(digits) % 60

    def make_conv(self, user_helper, conv_name, conv_type=u'my_conv', **kw):
        return user_helper.create_conversation(conv_type, name=conv_name, **kw)

    @inlineCallbacks
    def test_bucket_for_conversation(self):
        worker = yield self.get_metrics_worker(needs_hash=True)
        user_helper = yield self.vumi_helper.make_user(u'acc1')
        conv1 = yield self.make_conv(user_helper, u'conv1')

        bucket = worker.bucket_for_conversation(conv1.key)
        self.assertEqual(bucket, hash(conv1.key) % 60)

    def assert_conversations_bucketed(self, worker, expected):
        expected = expected.copy()
        buckets = copy.deepcopy(worker._buckets)
        for key in range(60):
            buckets[key] = sorted(buckets[key])
            expected[key] = sorted(
                (c.user_account.key, c.key, u'my_conv_application')
                for c in expected.get(key, []))
            if buckets[key] == expected[key]:
                del buckets[key]
                del expected[key]
        self.assertEqual(buckets, expected)

    @inlineCallbacks
    def test_populate_conversation_buckets(self):
        worker = yield self.get_metrics_worker()

        user_helper = yield self.vumi_helper.make_user(u'acc1')
        conv1 = yield self.make_conv(user_helper, u'conv1', started=True)
        conv2a = yield self.make_conv(user_helper, u'conv2a', started=True)
        conv2b = yield self.make_conv(user_helper, u'conv2b', started=True)
        conv4 = yield self.make_conv(user_helper, u'conv4', started=True)
        for conv in [conv1, conv2a, conv2b, conv4]:
            self.conversation_names[conv.key] = conv.name

        self.assert_conversations_bucketed(worker, {})
        with LogCatcher(message='Scheduled') as lc:
            yield worker.populate_conversation_buckets()
            [log_msg] = lc.messages()
        self.assert_conversations_bucketed(worker, {
            1: [conv1],
            2: [conv2a, conv2b],
            4: [conv4],
        })
        # We may have tombstone keys from accounts created (and deleted) by
        # previous tests, so we replace the account count in the log message
        # we're asserting on.
        log_msg = re.sub(r'in \d account', 'in 1 account', log_msg)
        self.assertEqual(log_msg, "Scheduled metrics commands for"
                         " 4 conversations in 1 accounts.")

    @inlineCallbacks
    def test_process_bucket(self):
        worker = yield self.get_metrics_worker()

        user_helper = yield self.vumi_helper.make_user(u'acc1')
        conv1 = yield self.make_conv(user_helper, u'conv1', started=True)
        conv2a = yield self.make_conv(user_helper, u'conv2a', started=True)
        conv2b = yield self.make_conv(user_helper, u'conv2b', started=True)
        conv4 = yield self.make_conv(user_helper, u'conv4', started=True)
        for conv in [conv1, conv2a, conv2b, conv4]:
            self.conversation_names[conv.key] = conv.name

        self.assert_conversations_bucketed(worker, {})
        yield worker.populate_conversation_buckets()
        yield worker.process_bucket(2)
        self.assert_conversations_bucketed(worker, {
            1: [conv1],
            4: [conv4],
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
        user1_helper = yield self.vumi_helper.make_user(u'acc1')
        user2_helper = yield self.vumi_helper.make_user(u'acc2')
        user3_helper = yield self.vumi_helper.make_user(u'acc3')
        yield worker.redis.sadd(
            'disabled_metrics_accounts', user3_helper.account_key)
        yield worker.redis.sadd('metrics_accounts', user2_helper.account_key)

        account_keys = yield worker.find_account_keys()
        self.assertEqual(
            sorted([user1_helper.account_key, user2_helper.account_key]),
            sorted(account_keys))

    @inlineCallbacks
    def test_find_conversations_for_account(self):
        worker = yield self.get_metrics_worker()
        user_helper = yield self.vumi_helper.make_user(u'acc1')
        akey = user_helper.account_key

        conv1 = yield self.make_conv(user_helper, u'conv1', started=True)
        yield self.make_conv(user_helper, u'conv2', archived=True)
        yield self.make_conv(user_helper, u'conv3')

        conversation_keys = yield worker.find_conversations_for_account(akey)
        self.assertEqual(conversation_keys, [conv1.key])

    @inlineCallbacks
    def test_send_metrics_command(self):
        worker = yield self.get_metrics_worker()
        user_helper = yield self.vumi_helper.make_user(u'acc1')
        conv1 = yield self.make_conv(user_helper, u'conv1', started=True)

        yield worker.send_metrics_command(
            conv1.user_account.key, conv1.key, 'my_conv_application')
        [cmd] = self.vumi_helper.get_dispatched_commands()

        self.assertEqual(cmd['worker_name'], 'my_conv_application')
        self.assertEqual(cmd['kwargs']['conversation_key'], conv1.key)
        self.assertEqual(
            cmd['kwargs']['user_account_key'], user_helper.account_key)

    @inlineCallbacks
    def setup_metric_loop_conversations(self, worker):
        user1_helper = yield self.vumi_helper.make_user(u'acc1')
        conv0 = yield self.make_conv(user1_helper, u'conv0', started=True)
        conv1 = yield self.make_conv(user1_helper, u'conv1', started=True)
        user2_helper = yield self.vumi_helper.make_user(u'acc2')
        conv2 = yield self.make_conv(user2_helper, u'conv2', started=True)
        conv3 = yield self.make_conv(user2_helper, u'conv3', started=True)
        for conv in [conv0, conv1, conv2, conv3]:
            self.conversation_names[conv.key] = conv.name

        returnValue([conv0, conv1, conv2, conv3])

    @inlineCallbacks
    def test_metrics_loop_func_bucket_zero(self):
        worker = yield self.get_metrics_worker()
        convs = yield self.setup_metric_loop_conversations(worker)
        [conv0, conv1, conv2, conv3] = convs

        self.assertEqual(worker._current_bucket, 0)
        yield worker.metrics_loop_func()
        self.assertEqual(worker._current_bucket, 1)

        cmds = self.vumi_helper.get_dispatched_commands()
        conv_keys = [c.payload['kwargs']['conversation_key'] for c in cmds]
        self.assertEqual(conv_keys, [conv0.key])

        self.assert_conversations_bucketed(worker, {
            1: [conv1],
            2: [conv2],
            3: [conv3],
        })

    @inlineCallbacks
    def test_metrics_loop_func_bucket_nonzero(self):
        worker = yield self.get_metrics_worker()
        convs = yield self.setup_metric_loop_conversations(worker)
        [conv0, conv1, conv2, conv3] = convs
        yield worker.populate_conversation_buckets()

        worker._current_bucket = 1
        yield worker.metrics_loop_func()
        self.assertEqual(worker._current_bucket, 2)

        cmds = self.vumi_helper.get_dispatched_commands()
        conv_keys = [c['kwargs']['conversation_key'] for c in cmds]
        self.assertEqual(conv_keys, [conv1.key])

        self.assert_conversations_bucketed(worker, {
            0: [conv0],
            2: [conv2],
            3: [conv3],
        })
