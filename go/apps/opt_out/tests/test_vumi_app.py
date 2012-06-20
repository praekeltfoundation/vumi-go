# -*- coding: utf-8 -*-

"""Tests for go.apps.opt_out application"""

import json
import uuid

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis
from vumi.persist.txriak_manager import TxRiakManager

from go.apps.opt_out.vumi_app import OptOutApplication
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import CeleryTestMixIn, DummyConsumerFactory
from go.vumitools.account import AccountStore
from go.vumitools.opt_out import OptOutStore


def dummy_consumer_factory_factory_factory(publish_func):
    def dummy_consumer_factory_factory():
        dummy_consumer_factory = DummyConsumerFactory()
        dummy_consumer_factory.publish = publish_func
        return dummy_consumer_factory
    return dummy_consumer_factory_factory


class TestOptOutApplication(ApplicationTestCase, CeleryTestMixIn):

    application_class = OptOutApplication
    transport_type = u'sms'
    timeout = 2

    @inlineCallbacks
    def setUp(self):
        super(TestOptOutApplication, self).setUp()

        self._fake_redis = FakeRedis()
        self.config = {
            'redis_cls': lambda **kw: self._fake_redis,
            'worker_name': 'opt_out_application',
            'message_store': {
                'store_prefix': 'test.',
            },
            'riak_manager': {
                'bucket_prefix': 'test.',
            },
        }

        # Setup the OptOutApplication
        self.app = yield self.get_application(self.config)

        # Setup the command dispatcher so we cand send it commands
        self.cmd_dispatcher = yield self.get_application({
            'transport_name': 'cmd_dispatcher',
            'worker_names': ['opt_out_application'],
            }, cls=CommandDispatcher)

        # Setup Celery so that it uses FakeAMQP instead of the real one.
        self.manager = self.app.store.manager  # YOINK!
        self.account_store = AccountStore(self.manager)
        self.VUMI_COMMANDS_CONSUMER = dummy_consumer_factory_factory_factory(
            self.publish_command)
        self.setup_celery_for_tests()

        # Create a test user account
        self.user_account = yield self.account_store.new_user(u'testuser')
        self.user_api = VumiUserApi(self.user_account.key, self.config,
                                        TxRiakManager)

        # Add tags
        self.user_api.api.declare_tags([("pool", "tag1"), ("pool", "tag2")])
        self.user_api.api.set_pool_metadata("pool", {
            "transport_type": self.transport_type,
            "msg_options": {
                "transport_name": self.transport_name,
            },
        })

        # Give a user access to a tagpool
        self.user_api.api.account_store.tag_permissions(uuid.uuid4().hex,
            tagpool=u"pool", max_keys=None)

        self.conversation = yield self.create_conversation(u'opt_out',
            u'Subject', u'Message',
            delivery_tag_pool=u'pool',
            delivery_class=self.transport_type)
        yield self.conversation.save()

    @inlineCallbacks
    def create_conversation(self, conversation_type, subject, message,
        **kwargs):
        conversation = yield self.user_api.new_conversation(
            conversation_type, subject, message, **kwargs)
        yield conversation.save()
        returnValue(self.user_api.wrap_conversation(conversation))

    @inlineCallbacks
    def opt_out(self, from_addr, to_addr, content, transport_type=None):
        if transport_type:
            self.transport_type = transport_type
        msg = TransportUserMessage(
            to_addr=to_addr,
            from_addr=from_addr,
            content=content,
            session_event=None,
            transport_name=self.transport_name,
            transport_type=self.transport_type,
            helper_metadata={"go": {"user_account": "testuser"}},
            )
        yield self.dispatch(msg)

    def publish_command(self, cmd_dict):
        data = json.dumps(cmd_dict)
        self._amqp.publish_raw('vumi', 'vumi.api', data)

    @inlineCallbacks
    def wait_for_messages(self, nr_of_messages, total_length):
        msgs = yield self.wait_for_dispatched_messages(total_length)
        returnValue(msgs[-1 * nr_of_messages:])

    @inlineCallbacks
    def tearDown(self):
        self.restore_celery()
        self._fake_redis.teardown()
        yield self.app.manager.purge_all()
        yield super(TestOptOutApplication, self).tearDown()

    @inlineCallbacks
    def test_sms_opt_out(self):
        yield self.conversation.start()
        yield self.opt_out("12345", "666", "STOP")
        [msg] = yield self.wait_for_dispatched_messages(1)
        self.assertEqual(msg.get('content'),
                "You have opted out")
        opt_out_store = OptOutStore(self.manager, "testuser")
        opt_out = yield opt_out_store.get_opt_out("msisdn", "12345")
        self.assertNotEqual(opt_out, None)

    @inlineCallbacks
    def test_http_opt_out(self):
        yield self.conversation.start()
        yield self.opt_out("12345", "666", "STOP", "http_api")
        [msg] = yield self.wait_for_dispatched_messages(1)
        self.assertEqual(msg.get('content'),
                '{"msisdn":"12345","opted_in": false}')
        opt_out_store = OptOutStore(self.manager, "testuser")
        opt_out = yield opt_out_store.get_opt_out("msisdn", "12345")
        self.assertNotEqual(opt_out, None)
