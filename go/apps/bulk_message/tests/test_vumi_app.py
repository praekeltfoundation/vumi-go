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
from go.vumitools.api import VumiUserApi, VumiApiCommand
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
            'riak': {
                'bucket_prefix': 'test.',
                },
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
            name=u'First', surname=u'Contact', msisdn=u'27831234567',
            groups=[group])
        contact2 = yield user_api.contact_store.new_contact(
            name=u'Second', surname=u'Contact', msisdn=u'27831234568',
            groups=[group])
        conversation = yield user_api.new_conversation(
            u'bulk_message', u'Subject', u'Message', delivery_tag_pool=u"pool",
            delivery_class=u'sms')
        conversation.add_group(group)
        yield conversation.save()
        conversation = user_api.wrap_conversation(conversation)

        yield conversation.start()

        # batch_id
        [batch_id] = conversation.batches.keys()

        # check commands made it through to the dispatcher and the vumi_app
        [disp_cmd] = self.get_dispatcher_commands()
        self.assertEqual(disp_cmd['command'], 'start')
        [bulk_cmd] = self.get_bulk_message_commands()
        self.assertEqual(bulk_cmd['command'], 'start')
        yield self._amqp.kick_delivery()

        # assert that we've sent the message to the two contacts
        msgs = yield self.get_dispatched_messages()
        msgs.sort(key=lambda msg: msg['to_addr'])
        [msg1, msg2] = msgs

        # check that the right to_addr & from_addr are set and that the content
        # of the message equals conversation.message
        self.assertEqual(msg1['to_addr'], contact1.msisdn)
        self.assertEqual(msg2['to_addr'], contact2.msisdn)

        # check tags and user accounts
        for msg in msgs:
            tag = msg['helper_metadata']['tag']['tag']
            user_account_key = msg['helper_metadata']['go']['user_account']
            self.assertEqual(tag, ["pool", "tag1"])
            self.assertEqual(user_account_key, user_account.key)

        batch_status = self.app.store.batch_status(batch_id)
        self.assertEqual(batch_status['sent'], 2)
        dbmsgs = yield self.app.store.batch_messages(batch_id)
        dbmsgs.sort(key=lambda msg: msg['to_addr'])
        [dbmsg1, dbmsg2] = dbmsgs
        self.assertEqual(dbmsg1, msg1)
        self.assertEqual(dbmsg2, msg2)

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

    @inlineCallbacks
    def test_send_message_command(self):
        user_account_key = "4f5gfdtrfe44rgffserf"
        msg_options = {
            'transport_name': 'sphex_transport',
            'from_addr': '666666',
            'transport_type': 'sphex',
            "helper_metadata": {
                "go": {
                    "user_account": user_account_key
                },
                'tag': {
                    'tag': ['pool', 'tag1']
                },
                'transport_type': 'sphex'
            }
        }
        sm_cmd = VumiApiCommand.command(
                self.app.worker_name,
                "send_message",
                command_data = {
                    "batch_id": "345dt54fgtffdsft54ffg",
                    "to_addr": "123456",
                    "content": "hello world",
                    "msg_options": msg_options
                },
                )
        yield self.dispatch(sm_cmd, rkey='%s.control' % self.app.worker_name)

        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg.payload['to_addr'], "123456")
        self.assertEqual(msg.payload['content'], "hello world")
        print msg.payload
