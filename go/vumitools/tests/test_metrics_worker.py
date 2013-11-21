"""Tests for go.vumitools.metrics_worker."""

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock, LoopingCall

from vumi.tests.helpers import VumiTestCase

from go.vumitools import metrics_worker
from go.vumitools.tests.helpers import VumiApiHelper


class TestGoMetricsWorker(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = VumiApiHelper()
        self.add_cleanup(self.vumi_helper.cleanup)
        yield self.vumi_helper.setup_vumi_api()
        self.clock = Clock()
        self.patch(metrics_worker, 'LoopingCall', self.looping_call)

    def get_metrics_worker(self, config=None, start=True):
        config = self.vumi_helper.mk_config(config or {})
        return self.vumi_helper.get_worker_helper().get_worker(
            metrics_worker.GoMetricsWorker, config, start=start)

    def rkey(self, name):
        return name

    def looping_call(self, *args, **kwargs):
        looping_call = LoopingCall(*args, **kwargs)
        looping_call.clock = self.clock
        return looping_call

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
    def test_metrics_poller(self):
        polls = []
        # Replace metrics worker with one that hasn't started yet.
        worker = yield self.get_metrics_worker(start=False)
        worker.metrics_loop_func = lambda: polls.append(None)
        self.assertEqual(0, len(polls))
        # Start worker.
        yield worker.startWorker()
        self.assertEqual(1, len(polls))
        # Pass time, but not enough to trigger a metric run.
        self.clock.advance(250)
        self.assertEqual(1, len(polls))
        # Pass time, trigger a metric run.
        self.clock.advance(50)
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

        conv1 = yield user_helper.create_conversation(
            u'dummy_conv', name=u'conv1', started=True)
        yield user_helper.create_conversation(
            u'dummy_conv', name=u'conv2', archived=True)
        yield user_helper.create_conversation(u'dummy_conv', name=u'conv3')

        conversations = yield worker.find_conversations_for_account(akey)
        self.assertEqual([c.key for c in conversations], [conv1.key])

    @inlineCallbacks
    def test_send_metrics_command(self):
        worker = yield self.get_metrics_worker()
        user_helper = yield self.vumi_helper.make_user(u'acc1')

        conv1 = yield user_helper.create_conversation(
            u'dummy_conv', name=u'conv1', started=True)

        yield worker.send_metrics_command(conv1)
        [cmd] = self.vumi_helper.get_dispatched_commands()

        self.assertEqual(cmd['worker_name'], 'dummy_conv_application')
        self.assertEqual(cmd['kwargs']['conversation_key'], conv1.key)
        self.assertEqual(
            cmd['kwargs']['user_account_key'], user_helper.account_key)

    @inlineCallbacks
    def test_metrics_loop_func(self):
        def no_looping(*args, **kw):
            return self.looping_call(lambda: None)
        self.patch(metrics_worker, 'LoopingCall',
                   no_looping)

        worker = yield self.get_metrics_worker()
        user1_helper = yield self.vumi_helper.make_user(u'acc1')
        user2_helper = yield self.vumi_helper.make_user(u'acc2')

        conv1 = yield user1_helper.create_conversation(
            u'dummy_conv', name=u'conv1', started=True)
        conv2 = yield user1_helper.create_conversation(
            u'dummy_conv', name=u'conv2', started=True)
        conv3 = yield user2_helper.create_conversation(
            u'dummy_conv', name=u'conv3', started=True)
        conv4 = yield user2_helper.create_conversation(
            u'dummy_conv', name=u'conv4', started=True)

        yield worker.metrics_loop_func()

        cmds = self.vumi_helper.get_dispatched_commands()
        conv_keys = [c['kwargs']['conversation_key'] for c in cmds]
        self.assertEqual(sorted(conv_keys),
                         sorted(c.key for c in [conv1, conv2, conv3, conv4]))
