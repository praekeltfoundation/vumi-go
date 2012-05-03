# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.dispatchers.tests.test_base import DispatcherTestCase
from vumi.dispatchers.base import BaseDispatchWorker
from vumi.middleware.tagger import TaggingMiddleware
from vumi.tests.utils import FakeRedis, LogCatcher
from vumi.application.tagpool import TagpoolManager

from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiApiCommand
from go.vumitools.conversation import ConversationStore


class CommandDispatcherTestCase(ApplicationTestCase):

    application_class = CommandDispatcher

    @inlineCallbacks
    def setUp(self):
        super(CommandDispatcherTestCase, self).setUp()
        self._fake_redis = FakeRedis()
        self.api = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            'worker_names': ['worker_1', 'worker_2'],
        })

    def tearDown(self):
        self._fake_redis.teardown()
        return super(CommandDispatcherTestCase, self).tearDown()

    def publish_command(self, cmd):
        return self.dispatch(cmd, rkey='vumi.api')

    @inlineCallbacks
    def test_forwarding_to_worker_name(self):
        api_cmd = VumiApiCommand.command('worker_1', 'foo')
        yield self.publish_command(api_cmd)
        [dispatched] = self._amqp.get_messages('vumi', 'worker_1.control')
        self.assertEqual(dispatched, api_cmd)

    @inlineCallbacks
    def test_unknown_worker_name(self):
        with LogCatcher() as logs:
            yield self.publish_command(
                VumiApiCommand.command('no-worker', 'foo'))
            [error] = logs.errors
            self.assertTrue("No worker publisher available" in
                                error['message'][0])

    @inlineCallbacks
    def test_badly_constructed_command(self):
        with LogCatcher() as logs:
            yield self.publish_command(VumiApiCommand())
            [error] = logs.errors
            self.assertTrue("No worker publisher available" in
                                error['message'][0])


class GoApplicationRouterTestCase(DispatcherTestCase):

    dispatcher_class = BaseDispatchWorker
    transport_name = 'test_transport'
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        yield super(GoApplicationRouterTestCase, self).setUp()
        self.dispatcher = yield self.get_dispatcher({
            'router_class': 'go.vumitools.api_worker.GoApplicationRouter',
            'transport_names': [
                self.transport_name,
            ],
            'exposed_names': [
                'app_1',
                'app_2',
            ],
            'conversation_mappings': {
                'bulk_message': 'app_1',
                'survey': 'app_2',
            }
        })
        self.r_server = FakeRedis()
        self.tpm = TagpoolManager(self.r_server, 'testpool')
        self.tpm.declare_tags([('xmpp', 'test1@xmpp.org')])

        # get the router to test
        self.router = self.dispatcher._router
        self.manager = self.router.manager
        # monkey patch the redis server
        self.message_store = self.router.message_store
        self.message_store.r_server = self.r_server

        self.account_store = self.router.account_store

        self.account = yield self.account_store.new_user(u'user')
        self.conversation_store = ConversationStore.from_user_account(
                                                                self.account)
        self.conversation = yield self.conversation_store.new_conversation(
            u'bulk_message', u'subject', u'message')

    @inlineCallbacks
    def tearDown(self):
        yield self.manager.purge_all()
        yield super(GoApplicationRouterTestCase, self).tearDown()

    @inlineCallbacks
    def test_tag_retrieval_and_dispatching(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name=self.transport_name)

        tag = self.tpm.acquire_tag('xmpp')
        batch_id = yield self.message_store.batch_start([tag],
            user_account=unicode(self.account.key))
        self.conversation.batches.add_key(batch_id)
        self.conversation.save()

        TaggingMiddleware.add_tag_to_msg(msg, tag)
        with LogCatcher() as log:
            yield self.dispatch(msg, self.transport_name)
            self.assertEqual(log.errors, [])
        [dispatched] = self.get_dispatched_messages('app_1',
                                                    direction='inbound')
        conv_metadata = dispatched['helper_metadata']['conversations']
        self.assertEqual(conv_metadata, {
            'conversation_key': self.conversation.key,
            'conversation_type': self.conversation.conversation_type,
        })

    @inlineCallbacks
    def test_no_tag(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name='xmpp_transport')
        with LogCatcher() as log:
            yield self.dispatch(msg, self.transport_name)
            [error] = log.errors
            self.assertTrue('No application setup' in error['message'][0])

    @inlineCallbacks
    def test_unknown_tag(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name='xmpp_transport')
        TaggingMiddleware.add_tag_to_msg(msg, ('this', 'does not exist'))
        with LogCatcher() as log:
            yield self.dispatch(msg, self.transport_name)
            [err1, err2] = log.errors
            self.assertTrue('Cannot find current tag for' in
                                    err1['message'][0])
            self.assertTrue('No application setup' in err2['message'][0])
