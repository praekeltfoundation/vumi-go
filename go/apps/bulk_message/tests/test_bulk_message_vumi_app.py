# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

import json

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportEvent, TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis
from vumi.persist.txriak_manager import TxRiakManager

from go.apps.bulk_message.vumi_app import BulkMessageApplication
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import CeleryTestMixIn, DummyConsumerFactory
from go.vumitools.account import AccountStore


def dummy_consumer_factory_factory_factory(publish_func):
    def dummy_consumer_factory_factory():
        dummy_consumer_factory = DummyConsumerFactory()
        dummy_consumer_factory.publish = publish_func
        return dummy_consumer_factory
    return dummy_consumer_factory_factory


class TestBulkMessageApplication(ApplicationTestCase, CeleryTestMixIn):

    application_class = BulkMessageApplication
    timeout = 2

    @inlineCallbacks
    def setUp(self):
        super(TestBulkMessageApplication, self).setUp()
        self._fake_redis = FakeRedis()
        self.app = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            })
        self.cmd_dispatcher = yield self.get_application({
            'transport_name': 'cmd_dispatcher',
            'worker_names': ['bulk_message_application'],
            }, cls=CommandDispatcher)
        self.manager = self.app.store.manager  # YOINK!
        self.account_store = AccountStore(self.manager)
        self.VUMI_COMMANDS_CONSUMER = dummy_consumer_factory_factory_factory(
            self.publish_command)
        self.setup_celery_for_tests()

    @inlineCallbacks
    def tearDown(self):
        self.restore_celery()
        self._fake_redis.teardown()
        yield self.app.manager.purge_all()
        yield super(TestBulkMessageApplication, self).tearDown()

    def publish_command(self, cmd_dict):
        data = json.dumps(cmd_dict)
        self._amqp.publish_raw('vumi', 'vumi.api', data)

    def get_dispatcher_commands(self):
        return self._amqp.get_messages('vumi', 'vumi.api')

    def get_bulk_message_commands(self):
        return self._amqp.get_messages('vumi',
                                       "%s.control" % self.app.worker_name)

    def publish_event(self, **kw):
        event = TransportEvent(**kw)
        d = self.dispatch(event, rkey=self.rkey('event'))
        d.addCallback(lambda _result: event)
        return d

    def store_outbound(self, **kw):
        return self.app.store.add_outbound_message(self.mkmsg_out(**kw))

    @inlineCallbacks
    def test_start(self):
        user_account = yield self.account_store.new_user(u'testuser')
        user_api = VumiUserApi(user_account.key, {
                'redis_cls': lambda **kw: self._fake_redis,
                'riak_manager': {'bucket_prefix': 'test.'},
                }, TxRiakManager)
        user_api.api.declare_tags([("pool", "tag1"), ("pool", "tag2")])
        user_api.api.set_pool_metadata("pool", {
            "transport_type": "sphex",
            })
        group = yield user_api.contact_store.new_group(u'test group')
        contact1 = yield user_api.contact_store.new_contact(
            u'First', u'Contact', msisdn=u'27831234567', groups=[group])
        contact2 = yield user_api.contact_store.new_contact(
            u'Second', u'Contact', msisdn=u'27831234568', groups=[group])
        conversation = yield user_api.new_conversation(
            u'bulk_message', u'Subject', u'Message', delivery_tag_pool=u"pool")
        conversation = user_api.wrap_conversation(conversation)

        yield conversation.start()

        # check commands made it through to the dispatcher and the vumi_app
        [disp_cmd] = self.get_dispatcher_commands()
        self.assertEqual(disp_cmd['command'], 'start')
        [bulk_cmd] = self.get_bulk_message_commands()
        self.assertEqual(bulk_cmd['command'], 'start')

        # assert that we've sent the message to the one contact
        [msg] = yield self.get_dispatched_messages()
        # check that the right to_addr & from_addr are set and that the content
        # of the message equals conversation.message
        self.assertEqual(msg['to_addr'], 'to_addr')
        self.assertEqual(msg['from_addr'], 'from_addr')
        self.assertEqual(msg['content'], 'content')

        self.assertEqual(self.app.store.batch_status(batch_id), {
                'ack': 0,
                'delivery_report': 0,
                'message': 1,
                'sent': 1,
                })
        [dbmsg] = yield self.app.store.batch_messages(batch_id)
        self.assertEqual(dbmsg, msg)

    @inlineCallbacks
    def test_consume_ack(self):
        yield self.store_outbound(message_id='123')
        ack_event = yield self.publish_event(user_message_id='123',
                                             event_type='ack',
                                             sent_message_id='xyz')
        [event] = yield self.app.store.message_events('123')
        self.assertEqual(event, ack_event)

    @inlineCallbacks
    def test_consume_delivery_report(self):
        yield self.store_outbound(message_id='123')
        dr_event = yield self.publish_event(user_message_id='123',
                                            event_type='delivery_report',
                                            delivery_status='delivered')
        [event] = yield self.app.store.message_events('123')
        self.assertEqual(event, dr_event)

    @inlineCallbacks
    def test_consume_user_message(self):
        msg = self.mkmsg_in()
        yield self.dispatch(msg)
        dbmsg = yield self.app.store.get_inbound_message(msg['message_id'])
        self.assertEqual(dbmsg, msg)

    @inlineCallbacks
    def test_close_session(self):
        msg = self.mkmsg_in(session_event=TransportUserMessage.SESSION_CLOSE)
        yield self.dispatch(msg)
        dbmsg = yield self.app.store.get_inbound_message(msg['message_id'])
        self.assertEqual(dbmsg, msg)
