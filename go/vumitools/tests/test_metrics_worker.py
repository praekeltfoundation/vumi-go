"""Tests for go.vumitools.metrics_worker."""

from datetime import datetime

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock, LoopingCall

from vumi.tests.utils import VumiWorkerTestCase

from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools import metrics_worker


class GoMetricsWorkerTestCase(VumiWorkerTestCase, GoPersistenceMixin):
    use_riak = True

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        super(GoMetricsWorkerTestCase, self).setUp()
        self.clock = Clock()
        self.patch(metrics_worker, 'LoopingCall', self.looping_call)
        self.worker = yield self.get_metrics_worker()

    @inlineCallbacks
    def tearDown(self):
        yield super(GoMetricsWorkerTestCase, self).tearDown()
        yield self._persist_tearDown()

    def get_metrics_worker(self, config=None, start=True):
        if config is None:
            config = {}
        return self.get_worker(
            self.mk_config(config), metrics_worker.GoMetricsWorker, start)

    def rkey(self, name):
        return name

    def looping_call(self, *args, **kwargs):
        looping_call = LoopingCall(*args, **kwargs)
        looping_call.clock = self.clock
        return looping_call

    def make_account(self, username):
        return self.mk_user(self.worker.vumi_api, username)

    def make_conv(self, user_api, conv_name, conv_type=u'my_conv'):
        return user_api.conversation_store.new_conversation(
            conv_type, conv_name, {})

    def start_conv(self, conv):
        conv.batches.add_key(u'batch-%s' % (conv.key,))
        conv.set_status_started()
        return conv.save()

    def end_conv(self, conv):
        conv.end_timestamp = datetime.utcnow()
        conv.set_status_finished()
        return conv.save()

    @inlineCallbacks
    def test_metrics_poller(self):
        polls = []
        # Replace metrics worker with one that hasn't started yet.
        yield self.worker.stopWorker()
        self.worker = yield self.get_metrics_worker(start=False)
        self.worker.metrics_loop_func = lambda: polls.append(None)
        self.assertEqual(0, len(polls))
        # Start worker.
        yield self.worker.startWorker()
        self.assertEqual(1, len(polls))
        # Pass time, but not enough to trigger a metric run.
        self.clock.advance(250)
        self.assertEqual(1, len(polls))
        # Pass time, trigger a metric run.
        self.clock.advance(50)
        self.assertEqual(2, len(polls))

    @inlineCallbacks
    def test_find_accounts(self):
        acc1 = yield self.make_account(u'acc1')
        acc2 = yield self.make_account(u'acc2')
        yield self.make_account(u'acc3')
        yield self.worker.redis.sadd('metrics_accounts', acc1.key)
        yield self.worker.redis.sadd('metrics_accounts', acc2.key)

        account_keys = yield self.worker.find_account_keys()
        self.assertEqual(sorted([acc1.key, acc2.key]), sorted(account_keys))

    @inlineCallbacks
    def test_find_conversations_for_account(self):
        acc1 = yield self.make_account(u'acc1')
        akey = acc1.key
        user_api = self.worker.vumi_api.get_user_api(akey)

        conv1 = yield self.make_conv(user_api, u'conv1')
        yield self.end_conv(conv1)
        conv2 = yield self.make_conv(user_api, u'conv2')
        yield self.start_conv(conv2)
        yield self.make_conv(user_api, u'conv3')

        conversations = yield self.worker.find_conversations_for_account(akey)
        self.assertEqual([c.key for c in conversations], [conv2.key])

    @inlineCallbacks
    def test_send_metrics_command(self):
        acc1 = yield self.make_account(u'acc1')
        akey = acc1.key
        user_api = self.worker.vumi_api.get_user_api(akey)

        conv1 = yield self.make_conv(user_api, u'conv1')
        yield self.start_conv(conv1)

        yield self.worker.send_metrics_command(conv1)
        [cmd] = self._get_dispatched('vumi.api')
        self.assertEqual(cmd.payload['kwargs']['conversation_key'], conv1.key)
        self.assertEqual(cmd.payload['kwargs']['user_account_key'], akey)

    @inlineCallbacks
    def test_metrics_loop_func(self):
        acc1 = yield self.make_account(u'acc1')
        acc2 = yield self.make_account(u'acc2')
        yield self.worker.redis.sadd('metrics_accounts', acc1.key)
        yield self.worker.redis.sadd('metrics_accounts', acc2.key)
        user_api1 = self.worker.vumi_api.get_user_api(acc1.key)
        user_api2 = self.worker.vumi_api.get_user_api(acc2.key)

        conv1 = yield self.make_conv(user_api1, u'conv1')
        yield self.start_conv(conv1)
        conv2 = yield self.make_conv(user_api1, u'conv2')
        yield self.start_conv(conv2)
        conv3 = yield self.make_conv(user_api2, u'conv3')
        yield self.start_conv(conv3)
        conv4 = yield self.make_conv(user_api2, u'conv4')
        yield self.start_conv(conv4)

        yield self.worker.metrics_loop_func()

        cmds = self._get_dispatched('vumi.api')
        conv_keys = [c.payload['kwargs']['conversation_key'] for c in cmds]
        self.assertEqual(sorted(conv_keys),
                         sorted(c.key for c in [conv1, conv2, conv3, conv4]))
