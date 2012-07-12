# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.dispatchers.tests.test_base import DispatcherTestCase
from vumi.dispatchers.base import BaseDispatchWorker
from vumi.middleware.tagger import TaggingMiddleware
from vumi.persist.txriak_manager import TxRiakManager
from vumi.persist.message_store import MessageStore
from vumi.tests.utils import FakeRedis, LogCatcher

from go.vumitools.api_worker import (
    CommandDispatcher, EventDispatcher)
from go.vumitools.handler import EventHandler, SendMessageCommandHandler
from go.vumitools.api import VumiApiCommand, VumiApiEvent, VumiUserApi
from go.vumitools.conversation import ConversationStore
from go.vumitools.account import AccountStore


class CommandDispatcherTestCase(ApplicationTestCase):

    application_class = CommandDispatcher

    @inlineCallbacks
    def setUp(self):
        super(CommandDispatcherTestCase, self).setUp()
        self._fake_redis = FakeRedis()
        self.api = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            'riak_manager': {'bucket_prefix': 'test.'},
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


class ToyHandler(EventHandler):
    def setup_handler(self):
        self.handled_events = []

    def handle_event(self, event, handler_config):
        self.handled_events.append((event, handler_config))


class EventDispatcherTestCase(ApplicationTestCase):

    application_class = EventDispatcher

    @inlineCallbacks
    def setUp(self):
        super(EventDispatcherTestCase, self).setUp()
        self._fake_redis = FakeRedis()
        self.ed = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            'riak_manager': {'bucket_prefix': 'test.'},
            'event_handlers': {
                    'handler1': '%s.ToyHandler' % __name__,
                    'handler2': '%s.ToyHandler' % __name__,
                    },
        })
        self.handler1 = self.ed.handlers['handler1']
        self.handler2 = self.ed.handlers['handler2']

    def tearDown(self):
        self._fake_redis.teardown()
        return super(EventDispatcherTestCase, self).tearDown()

    def publish_event(self, cmd):
        return self.dispatch(cmd, rkey='vumi.event')

    def mkevent(self, event_type, content, conv_key="conv_key",
                account_key="acct"):
        return VumiApiEvent.event(
            account_key, conv_key, event_type, content)

    @inlineCallbacks
    def test_handle_event(self):
        self.ed.account_config['acct'] = {
            ('conv_key', 'my_event'): [('handler1', {})]}
        event = self.mkevent("my_event", {"foo": "bar"})
        self.assertEqual([], self.handler1.handled_events)
        yield self.publish_event(event)
        self.assertEqual([(event, {})], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)

    @inlineCallbacks
    def test_handle_event_uncached(self):
        user_account = yield self.ed.account_store.new_user(u'dbacct')
        user_account.event_handler_config = [
            [['conv_key', 'my_event'], [('handler1', {})]]
            ]
        yield user_account.save()
        event = self.mkevent(
            "my_event", {"foo": "bar"}, account_key=user_account.key)
        self.assertEqual([], self.handler1.handled_events)
        yield self.publish_event(event)
        self.assertEqual([(event, {})], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)

    @inlineCallbacks
    def test_handle_events(self):
        self.ed.account_config['acct'] = {
            ('conv_key', 'my_event'): [('handler1', {'animal': 'puppy'})],
            ('conv_key', 'other_event'): [
                ('handler1', {'animal': 'kitten'}),
                ('handler2', {})
                ],
            }
        event = self.mkevent("my_event", {"foo": "bar"})
        event2 = self.mkevent("other_event", {"foo": "bar"})
        self.assertEqual([], self.handler1.handled_events)
        self.assertEqual([], self.handler2.handled_events)
        yield self.publish_event(event)
        yield self.publish_event(event2)
        self.assertEqual(
            [(event, {'animal': 'puppy'}), (event2, {'animal': 'kitten'})],
            self.handler1.handled_events)
        self.assertEqual([(event2, {})], self.handler2.handled_events)


class SendingEventDispatcherTestCase(ApplicationTestCase):
    timeout = 2
    application_class = EventDispatcher

    @inlineCallbacks
    def setUp(self):
        super(SendingEventDispatcherTestCase, self).setUp()
        self._fake_redis = FakeRedis()
        self.base_config = {
            'redis_cls': lambda **kw: self._fake_redis,
            'riak_manager': {'bucket_prefix': 'test.'},
            }
        ed_config = self.base_config.copy()
        ed_config.update({
                'event_handlers': {
                    'handler1': "%s.%s" % (
                        SendMessageCommandHandler.__module__,
                        SendMessageCommandHandler.__name__)
                    },
                })
        self.ed = yield self.get_application(ed_config)
        self.handler1 = self.ed.handlers['handler1']

    def tearDown(self):
        self._fake_redis.teardown()
        return super(SendingEventDispatcherTestCase, self).tearDown()

    def publish_event(self, cmd):
        return self.dispatch(cmd, rkey='vumi.event')

    def mkevent(self, event_type, content, conv_key="conv_key",
                account_key="acct"):
        return VumiApiEvent.event(
            account_key, conv_key, event_type, content)

    @inlineCallbacks
    def test_handle_events(self):
        user_account = yield self.ed.account_store.new_user(u'dbacct')
        yield user_account.save()

        user_api = VumiUserApi(
            user_account.key, self.base_config.copy(), TxRiakManager)
        user_api.api.declare_tags([("pool", "tag1")])
        user_api.api.set_pool_metadata("pool", {
            "transport_type": "other",
            "msg_options": {"transport_name": "other_transport"},
            })

        conversation = yield user_api.new_conversation(
                                    u'bulk_message', u'subject', u'message',
                                    delivery_tag_pool=u'pool',
                                    delivery_class=u'sms')

        conversation = user_api.wrap_conversation(conversation)
        yield conversation.start()

        user_account.event_handler_config = [
            [[conversation.key, 'my_event'], [('handler1', {
                'worker_name': 'other_worker',
                'conversation_key': 'other_conv',
                })]]
            ]
        yield user_account.save()

        event = self.mkevent("my_event",
                {"to_addr": "12345", "content": "hello"},
                account_key=user_account.key,
                conv_key=conversation.key)
        yield self.publish_event(event)

        [api_command] = self._amqp.get_messages('vumi', 'vumi.api')
        self.assertEqual(api_command['worker_name'], 'other_worker')
        self.assertEqual(api_command['kwargs']['command_data'], {
                'content': 'hello',
                'batch_id': conversation.batches.keys()[0],
                'to_addr': '12345',
                'msg_options': {
                    'transport_name': 'other_transport',
                    'helper_metadata': {
                        'go': {'user_account': user_account.key},
                        'tag': {'tag': ['pool', 'tag1']},
                        'transport_type': u'other'
                        },
                    'transport_type': 'other',
                    'from_addr': 'tag1',
                    }})


class GoApplicationRouterTestCase(DispatcherTestCase):

    dispatcher_class = BaseDispatchWorker
    transport_name = 'test_transport'

    @inlineCallbacks
    def setUp(self):
        yield super(GoApplicationRouterTestCase, self).setUp()
        self.r_server = FakeRedis()
        self.mdb_prefix = 'test_message_store'
        self.message_store_config = {
            'message_store': {
                'store_prefix': self.mdb_prefix,
            }
        }
        self.dispatcher = yield self.get_dispatcher({
            'router_class': 'go.vumitools.api_worker.GoApplicationRouter',
            'redis_clr': lambda: self.r_server,
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
        })

        # get the router to test
        self.manager = TxRiakManager.from_config({
                'bucket_prefix': self.mdb_prefix})
        self.account_store = AccountStore(self.manager)
        self.message_store = MessageStore(self.manager, self.r_server,
                                            self.mdb_prefix)

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
