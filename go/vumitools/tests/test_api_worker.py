# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.dispatchers.tests.test_base import DispatcherTestCase
from vumi.dispatchers.base import BaseDispatchWorker
from vumi.middleware.tagger import TaggingMiddleware
from vumi.tests.utils import LogCatcher

from go.vumitools.api_worker import CommandDispatcher, GoMessageMetadata
from go.vumitools.api import VumiApi, VumiUserApi, VumiApiCommand
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

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()

        self.vumi_api = yield VumiApi.from_config_async(self._persist_config)
        self.account = yield self.vumi_api.account_store.new_user(u'user')
        self.user_api = VumiUserApi(self.vumi_api, self.account.key)
        self.tag = ('xmpp', 'test1@xmpp.org')

    def tearDown(self):
        return self._persist_tearDown()

    def create_conversation(self, conversation_type=u'bulk_message',
                            subject=u'subject', message=u'message'):
        return self.user_api.conversation_store.new_conversation(
            conversation_type, subject, message)

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


class GoApplicationRouterTestCase(DispatcherTestCase):

    dispatcher_class = BaseDispatchWorker
    transport_name = 'test_transport'

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
                'optout_app',
            ],
            'upstream_transport': self.transport_name,
            'optout_transport': 'optout_app',
            'conversation_mappings': {
                'bulk_message': 'app_1',
                'survey': 'app_2',
            },
            'middleware': [
                {'optout_mw':
                    'go.vumitools.middleware.OptOutMiddleware'},
            ],
            'optout_mw': {
                'optout_keywords': ['stop']
            }
            })

        # get the router to test
        self.vumi_api = yield VumiApi.from_config_async(self._persist_config)

        self.account = yield self.vumi_api.account_store.new_user(u'user')
        self.user_api = VumiUserApi(self.vumi_api, self.account.key)
        self.conversation = (
            yield self.user_api.conversation_store.new_conversation(
                u'bulk_message', u'subject', u'message'))

    @inlineCallbacks
    def tearDown(self):
        yield self._persist_tearDown()
        yield super(GoApplicationRouterTestCase, self).tearDown()

    @inlineCallbacks
    def test_tag_retrieval_and_dispatching(self):
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
        batch_id = yield self.vumi_api.mdb.batch_start([tag],
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
