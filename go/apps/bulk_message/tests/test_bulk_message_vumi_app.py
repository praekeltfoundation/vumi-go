# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportEvent, TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from go.apps.bulk_message.vumi_app import BulkMessageApplication
from go.vumitools.api import VumiApiCommand, VumiUserApi
from go.vumitools.account import AccountStore


class TestBulkMessageApplication(ApplicationTestCase):

    application_class = BulkMessageApplication
    timeout = 2

    @inlineCallbacks
    def setUp(self):
        super(TestBulkMessageApplication, self).setUp()
        self._fake_redis = FakeRedis()
        self.app = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            })
        self.manager = self.app.store.manager  # YOINK!
        self.account_store = AccountStore(self.manager)

    @inlineCallbacks
    def tearDown(self):
        self._fake_redis.teardown()
        yield self.app.manager.purge_all()
        yield super(TestBulkMessageApplication, self).tearDown()

    def publish_command(self, cmd):
        return self.dispatch(cmd, rkey='%s.control' % (
                self.application_class.worker_name,))

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
                'riak_manager': {},
                }, self.manager)
        group = yield user_api.contact_store.new_group(u'test group')
        contact1 = yield user_api.contact_store.new_contact(
            u'First', u'Contact', msisdn=u'27831234567', groups=[group])
        contact2 = yield user_api.contact_store.new_contact(
            u'Second', u'Contact', msisdn=u'27831234568', groups=[group])
        conversation = yield user_api.new_conversation(
            u'bulk_message', u'Subject', u'Message')
        # TODO: 1) I need to acquire a tag here so it is linked to
        #       a batch_id
        #       2) I need to have an actual conversation so I can
        #       pass in the conversation_type and the conversation_key
        #       3) I need to have a contact that is part of this conversation
        #       and has a relevant to_addr set for the tag assigned
        #       4) I need to have an account object so I can add
        #       that info with DebitAccountMiddleware.add_user_to_payload
        #       5) msg_options can go since that info should be coming
        #       from the tagpool metadata and the app worker can extract
        #       that info.
        batch_id = yield self.app.store.batch_start([])
        cmd = VumiApiCommand.command(
            'dummy_worker', 'start',
            batch_id=batch_id,
            conversation_key=conversation.key,
            conversation_type=conversation.conversation_type,
            msg_options={})
        # publishes it to the app worker, handled by `process_start_command`
        yield self.publish_command(cmd)
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
