# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.dispatchers.tests.test_base import DispatcherTestCase
from vumi.dispatchers.base import BaseDispatchWorker
from vumi.middleware.tagger import TaggingMiddleware
from vumi.tests.utils import FakeRedis, LogCatcher

from go.vumitools.api_worker import CommandDispatcher, GoApplicationRouter
from go.vumitools.api import VumiApiCommand


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
                VumiApiCommand(worker_name='no-worker', command='foo'))
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


class TestGoApplicationRouter(GoApplicationRouter):

    def __init__(self, *args, **kwargs):
        super(TestGoApplicationRouter, self).__init__(*args, **kwargs)
        self.tag_to_batch_ids_map = {
            ('xmpp', 'test1@xmpp.org'): 'batch-id-1',
            ('xmpp', 'test2@xmpp.org'): 'batch-id-2',
        }
        self.batch_id_to_conversations_map = {
            'batch-id-1': {
                'conversation_id': '1', 'conversation_type': 'type_1',
            },
            'batch-id-2': {
                'conversation_type': '2', 'conversation_type': 'type_2',
            }
        }

    def get_conversation_for_tag(self, tag):
        batch_id = self.tag_to_batch_ids_map.get(tag)
        return self.batch_id_to_conversations_map.get(batch_id, {})


class GoApplicationRouterTestCase(DispatcherTestCase):

    dispatcher_class = BaseDispatchWorker
    transport_name = 'test_transport'
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        yield super(GoApplicationRouterTestCase, self).setUp()
        self.dispatcher = yield self.get_dispatcher({
            'router_class': 'go.vumitools.tests.test_api_worker.' \
                                'TestGoApplicationRouter',
            'transport_names': [
                self.transport_name,
            ],
            'exposed_names': [
                'app_1',
                'app_2',
            ],
            'conversation_mappings': {
                'type_1': 'app_1',
                'type_2': 'app_2',
            }
        })
        self.router = self.dispatcher._router

    @inlineCallbacks
    def tearDown(self):
        yield self.router.manager.purge_all()
        yield super(GoApplicationRouterTestCase, self).tearDown()

    @inlineCallbacks
    def test_tag_retrieval_and_dispatching(self):
        msg = self.mkmsg_in(transport_type='xmpp',
                                transport_name='xmpp_transport')
        TaggingMiddleware.add_tag_to_msg(msg, ('xmpp', 'test1@xmpp.org'))
        yield self.dispatch(msg, self.transport_name)
        [dispatched] = self.get_dispatched_messages('app_1',
                                                    direction='inbound')
        conv_metadata = dispatched['helper_metadata']['conversations']
        self.assertEqual(conv_metadata, {
            'conversation_id': '1',
            'conversation_type': 'type_1',
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
