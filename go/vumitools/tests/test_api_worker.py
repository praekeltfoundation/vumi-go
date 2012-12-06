# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.dispatchers.tests.test_base import DispatcherTestCase
from vumi.dispatchers.base import BaseDispatchWorker
from vumi.middleware.tagger import TaggingMiddleware
from vumi.tests.utils import LogCatcher

from go.vumitools.api_worker import (
    EventDispatcher, CommandDispatcher, GoMessageMetadata)
from go.vumitools.api import VumiApi, VumiApiCommand, VumiApiEvent
from go.vumitools.handler import EventHandler, SendMessageCommandHandler
from go.vumitools.tests.utils import AppWorkerTestCase, GoPersistenceMixin


class CommandDispatcherTestCase(AppWorkerTestCase):

    application_class = CommandDispatcher

    @inlineCallbacks
    def setUp(self):
        super(CommandDispatcherTestCase, self).setUp()
        self.api = yield self.get_application({
                'worker_names': ['worker_1', 'worker_2']})

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


class GoMessageMetadataTestCase(GoPersistenceMixin, TestCase):
    use_riak = True

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()

        self.vumi_api = yield VumiApi.from_config_async(self._persist_config)
        self._persist_riak_managers.append(self.vumi_api.manager)
        self._persist_redis_managers.append(self.vumi_api.redis)
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)
        self.tag = ('xmpp', 'test1@xmpp.org')

    def tearDown(self):
        return self._persist_tearDown()

    def create_conversation(self, conversation_type=u'bulk_message',
                            name=u'subject', config={u'content': u'message'}):
        return self.user_api.conversation_store.new_conversation(
            conversation_type, name, config)

    @inlineCallbacks
    def tag_conversation(self, conversation, tag):
        batch_id = yield self.vumi_api.mdb.batch_start([tag],
                            user_account=unicode(self.account.key))
        conversation.batches.add_key(batch_id)
        conversation.save()
        returnValue(batch_id)

    def mk_msg(self, to_addr, from_addr):
        return TransportUserMessage(to_addr=to_addr, from_addr=from_addr,
                                   transport_name="dummy_endpoint",
                                   transport_type="dummy_transport_type")

    def mk_md(self, message):
        return GoMessageMetadata(self.vumi_api, message)

    @inlineCallbacks
    def test_account_key_lookup(self):
        conversation = yield self.create_conversation()
        batch_key = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        self.assertEqual(msg['helper_metadata'],
                         {'tag': {'tag': list(self.tag)}})

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        account_key = yield md.get_account_key()
        self.assertEqual(account_key, self.account.key)
        self.assertEqual(msg['helper_metadata']['go'], {
                'batch_key': batch_key,
                'user_account': account_key,
                })

    @inlineCallbacks
    def test_batch_lookup(self):
        conversation = yield self.create_conversation()
        batch_key = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        self.assertEqual(msg['helper_metadata'],
                         {'tag': {'tag': list(self.tag)}})

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        msg_batch_key = yield md.get_batch_key()
        self.assertEqual(batch_key, msg_batch_key)
        self.assertEqual(msg['helper_metadata']['go'],
                         {'batch_key': batch_key})

    @inlineCallbacks
    def test_conversation_lookup(self):
        conversation = yield self.create_conversation()
        batch_key = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        self.assertEqual(msg['helper_metadata'],
                         {'tag': {'tag': list(self.tag)}})

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        conv_key, conv_type = yield md.get_conversation_info()
        self.assertEqual(conv_key, conversation.key)
        self.assertEqual(conv_type, conversation.conversation_type)
        self.assertEqual(msg['helper_metadata']['go'], {
                'batch_key': batch_key,
                'user_account': self.account.key,
                'conversation_key': conv_key,
                'conversation_type': conv_type,
                })

    @inlineCallbacks
    def test_rewrap(self):
        conversation = yield self.create_conversation()
        batch_key = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        self.assertEqual(msg['helper_metadata'],
                         {'tag': {'tag': list(self.tag)}})

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        msg_batch_key = yield md.get_batch_key()
        self.assertEqual(batch_key, msg_batch_key)
        self.assertEqual(msg['helper_metadata']['go'],
                         {'batch_key': batch_key})

        # We create a new wrapper around the same message object and make sure
        # the cached message store objects are still there in the new one.
        new_md = self.mk_md(msg)
        self.assertNotEqual(md, new_md)
        self.assertEqual(md._store_objects, new_md._store_objects)
        self.assertEqual(md._go_metadata, new_md._go_metadata)

        # We create a new wrapper around the a copy of the message object and
        # make sure the message store object cache is empty, but the metadata
        # remains.
        other_md = self.mk_md(msg.copy())
        self.assertNotEqual(md, other_md)
        self.assertEqual({}, other_md._store_objects)
        self.assertEqual(md._go_metadata, other_md._go_metadata)


class ToyHandler(EventHandler):
    def setup_handler(self):
        self.handled_events = []

    def handle_event(self, event, handler_config):
        self.handled_events.append((event, handler_config))


class EventDispatcherTestCase(AppWorkerTestCase):

    application_class = EventDispatcher

    @inlineCallbacks
    def setUp(self):
        yield super(EventDispatcherTestCase, self).setUp()
        self.ed = yield self.get_application(self.mk_config({
            'event_handlers': {
                    'handler1': '%s.ToyHandler' % __name__,
                    'handler2': '%s.ToyHandler' % __name__,
                    },
        }))
        self.handler1 = self.ed.handlers['handler1']
        self.handler2 = self.ed.handlers['handler2']

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
        user_account = yield self.mk_user(self.ed.vumi_api, u'dbacct')
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


class SendingEventDispatcherTestCase(AppWorkerTestCase):
    application_class = EventDispatcher

    @inlineCallbacks
    def setUp(self):
        yield super(SendingEventDispatcherTestCase, self).setUp()
        ed_config = self.mk_config({
                'event_handlers': {
                    'handler1': "%s.%s" % (
                        SendMessageCommandHandler.__module__,
                        SendMessageCommandHandler.__name__)
                    },
                })
        self.ed = yield self.get_application(ed_config)
        self.handler1 = self.ed.handlers['handler1']

    def publish_event(self, cmd):
        return self.dispatch(cmd, rkey='vumi.event')

    def mkevent(self, event_type, content, conv_key="conv_key",
                account_key="acct"):
        return VumiApiEvent.event(
            account_key, conv_key, event_type, content)

    @inlineCallbacks
    def test_handle_events(self):
        user_account = yield self.mk_user(self.ed.vumi_api, u'dbacct')
        yield user_account.save()

        self.user_api = self.ed.vumi_api.get_user_api(user_account.key)
        yield self.user_api.api.declare_tags([("pool", "tag1")])
        yield self.user_api.api.set_pool_metadata("pool", {
            "transport_type": "other",
            "msg_options": {"transport_name": "other_transport"},
            })

        conversation = yield self.create_conversation(
            conversation_type=u'bulk_message', config={u'content': u'message'},
            delivery_tag_pool=u'pool', delivery_class=u'sms')

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

        [start_command, api_command] = self._amqp.get_messages('vumi',
                                                               'vumi.api')
        self.assertEqual(start_command['command'], 'start')
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
                        },
                    'transport_type': 'other',
                    'from_addr': 'tag1',
                    }})


class GoApplicationRouterTestCase(GoPersistenceMixin, DispatcherTestCase):
    use_riak = True
    dispatcher_class = BaseDispatchWorker
    transport_name = 'test_transport'

    @inlineCallbacks
    def setUp(self):
        yield super(GoApplicationRouterTestCase, self).setUp()
        self.dispatcher = yield self.get_dispatcher(self.mk_config({
            'router_class': 'go.vumitools.api_worker.GoApplicationRouter',
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
            }))

        # get the router to test
        self.vumi_api = yield VumiApi.from_config_async(self._persist_config)
        self._persist_riak_managers.append(self.vumi_api.manager)
        self._persist_redis_managers.append(self.vumi_api.redis)

        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)
        self.conversation = (
            yield self.user_api.conversation_store.new_conversation(
                u'bulk_message', u'subject', {u'content': u'message'}))

    @inlineCallbacks
    def test_tag_retrieval_and_message_dispatching(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name=self.transport_name)

        tag = ('xmpp', 'test1@xmpp.org')
        batch_id = yield self.vumi_api.mdb.batch_start([tag],
            user_account=unicode(self.account.key))
        self.conversation.batches.add_key(batch_id)
        yield self.conversation.save()

        TaggingMiddleware.add_tag_to_msg(msg, tag)
        with LogCatcher() as log:
            yield self.dispatch(msg, self.transport_name)
            self.assertEqual(log.errors, [])
        [dispatched] = self.get_dispatched_messages('app_1',
                                                    direction='inbound')
        go_metadata = dispatched['helper_metadata']['go']
        self.assertEqual(go_metadata['conversation_type'],
                         self.conversation.conversation_type)
        self.assertEqual(go_metadata['conversation_key'],
                         self.conversation.key)

    @inlineCallbacks
    def test_batch_id_retrieval_and_event_dispatching(self):
        # first create an outbound message and then publish an inbound
        # event for it.
        msg = self.mkmsg_out(transport_type='xmpp',
                                transport_name=self.transport_name)

        # Make sure stuff is tagged properly so it can be routed.
        tag = ('xmpp', 'test1@xmpp.org')
        batch_id = yield self.vumi_api.mdb.batch_start([tag],
            user_account=unicode(self.account.key))
        self.conversation.batches.add_key(batch_id)
        yield self.conversation.save()
        TaggingMiddleware.add_tag_to_msg(msg, tag)

        # Fake that it has been sent by storing it as a sent message
        yield self.vumi_api.mdb.add_outbound_message(msg, tag=tag,
            batch_id=batch_id)

        ack = self.mkmsg_ack(
            user_message_id=msg['message_id'],
            transport_name=self.transport_name)

        yield self.dispatch(ack, self.transport_name, 'event')

        [event] = self.get_dispatched_messages('app_1', direction='event')
        self.assertEqual(event['user_message_id'], msg['message_id'])

    @inlineCallbacks
    def test_batch_id_retrieval_and_event_dispatching_after_conv_close(self):
        # first create an outbound message and then publish an inbound
        # event for it.
        msg = self.mkmsg_out(transport_type='xmpp',
                                transport_name=self.transport_name)

        # Make sure stuff is tagged properly so it can be routed.
        tag = ('xmpp', 'test1@xmpp.org')
        batch_id = yield self.vumi_api.mdb.batch_start([tag],
            user_account=unicode(self.account.key))
        self.conversation.batches.add_key(batch_id)
        yield self.conversation.save()
        TaggingMiddleware.add_tag_to_msg(msg, tag)

        # Fake that it has been sent by storing it as a sent message
        yield self.vumi_api.mdb.add_outbound_message(msg, tag=tag,
            batch_id=batch_id)
        # mark the batch as done which is what happens when a conversation
        # is closed
        yield self.vumi_api.mdb.batch_done(batch_id)

        ack = self.mkmsg_ack(
            user_message_id=msg['message_id'],
            transport_name=self.transport_name)

        yield self.dispatch(ack, self.transport_name, 'event')

        [event] = self.get_dispatched_messages('app_1', direction='event')
        self.assertEqual(event['user_message_id'], msg['message_id'])

    @inlineCallbacks
    def test_no_tag(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name='xmpp_transport')
        with LogCatcher() as log:
            yield self.dispatch(msg, self.transport_name)
            [warning] = log.messages()
            self.assertTrue('No application setup' in warning)

    @inlineCallbacks
    def test_unknown_tag(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name='xmpp_transport')
        TaggingMiddleware.add_tag_to_msg(msg, ('this', 'does not exist'))
        with LogCatcher() as log:
            yield self.dispatch(msg, self.transport_name)
            [warning] = [msg for msg in log.messages()
                         if 'twisted.web.client' not in msg]
            self.assertTrue('No application setup' in warning)

    @inlineCallbacks
    def test_optout_message(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                            transport_name='xmpp_transport')
        msg['content'] = 'stop'
        tag = ('xmpp', 'test1@xmpp.org')
        batch_id = yield self.vumi_api.mdb.batch_start([tag],
            user_account=unicode(self.account.key))
        self.conversation.batches.add_key(batch_id)
        self.conversation.save()

        TaggingMiddleware.add_tag_to_msg(msg, tag)
        # Fake the opt-out middleware processing.
        msg['helper_metadata']['optout'] = {
            'optout': True, 'optout_keyword': 'stop'}
        yield self.dispatch(msg, self.transport_name)

        [dispatched] = self.get_dispatched_messages('optout_app',
                                                direction='inbound')
        helper_metadata = dispatched.get('helper_metadata', {})
        optout_metadata = helper_metadata.get('optout')
        self.assertEqual(optout_metadata, {
            'optout': True,
            'optout_keyword': 'stop',
        })
