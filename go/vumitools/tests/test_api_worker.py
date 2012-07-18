# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.dispatchers.tests.test_base import DispatcherTestCase
from vumi.dispatchers.base import BaseDispatchWorker
from vumi.middleware.tagger import TaggingMiddleware
from vumi.components.message_store import MessageStore
from vumi.tests.utils import LogCatcher

from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiApiCommand
from go.vumitools.conversation import ConversationStore
from go.vumitools.account import AccountStore
from go.vumitools.tests.utils import AppWorkerTestCase, GoPersistenceMixin


class CommandDispatcherTestCase(AppWorkerTestCase):

    application_class = CommandDispatcher

    @inlineCallbacks
    def setUp(self):
        super(CommandDispatcherTestCase, self).setUp()
        self.api = yield self.get_application(self.make_config({
                    'worker_names': ['worker_1', 'worker_2']}))

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


class GoApplicationRouterTestCase(GoPersistenceMixin, DispatcherTestCase):

    dispatcher_class = BaseDispatchWorker
    transport_name = 'test_transport'

    def make_config(self, config):
        return dict(self.base_config, **config)

    @inlineCallbacks
    def setUp(self):
        yield super(GoApplicationRouterTestCase, self).setUp()
        self._persist_setUp()
        self.redis = yield self.get_redis_manager()
        self.base_config = {
            'riak_manager': {'bucket_prefix': type(self).__module__},
            'redis': self.redis._client,
            }
        self.message_store_config = self.make_config({
                'r_prefix': 'test.'})
        self.dispatcher = yield self.get_dispatcher(self.make_config({
            'router_class': 'go.vumitools.api_worker.GoApplicationRouter',
            'r_prefix': 'test.',
            'transport_names': [
                self.transport_name,
            ],
            'exposed_names': [
                'app_1',
                'app_2',
                'optout_app',
            ],
            'upstream_transport': self.transport_name,
            'optout_transport': 'optout_app',
            'conversation_mappings': {
                'bulk_message': 'app_1',
                'survey': 'app_2',
            },
            'middleware': [
                {'account_mw':
                    'go.vumitools.middleware.LookupAccountMiddleware'},
                {'batch_mw':
                    'go.vumitools.middleware.LookupBatchMiddleware'},
                {'conversation_mw':
                    'go.vumitools.middleware.LookupConversationMiddleware'},
                {'optout_mw':
                    'go.vumitools.middleware.OptOutMiddleware'},
            ],
            'account_mw': self.message_store_config,
            'batch_mw': self.message_store_config,
            'conversation_mw': self.message_store_config,
            'optout_mw': {
                'optout_keywords': ['stop']
            }
        }))

        # get the router to test
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        self.message_store = MessageStore(self.manager, self.redis)

        self.account = yield self.account_store.new_user(u'user')
        self.conversation_store = ConversationStore.from_user_account(
                                                                self.account)
        self.conversation = yield self.conversation_store.new_conversation(
            u'bulk_message', u'subject', u'message')

    @inlineCallbacks
    def tearDown(self):
        yield self._persist_tearDown()
        yield super(GoApplicationRouterTestCase, self).tearDown()

    @inlineCallbacks
    def test_tag_retrieval_and_dispatching(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name=self.transport_name)

        tag = ('xmpp', 'test1@xmpp.org')
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
            [error] = log.errors
            self.assertTrue('No application setup' in error['message'][0])

    @inlineCallbacks
    def test_optout_message(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name='xmpp_transport')
        msg['content'] = 'stop'
        tag = ('xmpp', 'test1@xmpp.org')
        batch_id = yield self.message_store.batch_start([tag],
            user_account=unicode(self.account.key))
        self.conversation.batches.add_key(batch_id)
        self.conversation.save()

        TaggingMiddleware.add_tag_to_msg(msg, tag)
        yield self.dispatch(msg, self.transport_name)

        [dispatched] = self.get_dispatched_messages('optout_app',
                                                direction='inbound')
        helper_metadata = dispatched.get('helper_metadata', {})
        optout_metadata = helper_metadata.get('optout')
        self.assertEqual(optout_metadata, {
            'optout': True,
            'optout_keyword': 'stop',
        })
