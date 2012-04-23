# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportEvent, TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis
from vumi.middleware import TaggingMiddleware

from go.vumitools.bulk_send_application import BulkSendApplication
from go.vumitools.api import VumiApi, VumiApiCommand


class TestBulkSendApplication(ApplicationTestCase):

    application_class = BulkSendApplication

    @inlineCallbacks
    def setUp(self):
        super(TestBulkSendApplication, self).setUp()
        self._fake_redis = FakeRedis()
        self.app = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            })

        self.vumiapi = VumiApi({
            'redis_cls': lambda **kw: self._fake_redis,
        })
        self.vumiapi.declare_tags([("longcode", "default%s" % i) for i
                                      in range(10001, 10001 + 4)])


    def tearDown(self):
        self._fake_redis.teardown()
        super(TestBulkSendApplication, self).tearDown()

    def publish_command(self, cmd):
        return self.dispatch(cmd, rkey='%s.control' % (
                self.application_class.worker_name,))

    def publish_event(self, **kw):
        event = TransportEvent(**kw)
        d = self.dispatch(event, rkey=self.rkey('event'))
        d.addCallback(lambda _result: event)
        return d

    @inlineCallbacks
    def test_send(self):
        yield self.publish_command(VumiApiCommand.send('batch1',
                                                       'content',
                                                       {"from_addr": "from"},
                                                       'to_addr'))
        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg['to_addr'], 'to_addr')
        self.assertEqual(msg['content'], 'content')

        self.assertEqual(self.app.store.batch_status('batch1'), {
            'message': 1,
            'sent': 1,
            })
        [msg_id] = self.app.store.batch_messages('batch1')
        self.assertEqual(self.app.store.get_outbound_message(msg_id), msg)

    @inlineCallbacks
    def test_replies(self):
        """
        Test replies helper function
        """
        tag = self.vumiapi.acquire_tag("longcode")
        tagpool, to_addr = tag
        batch_id = self.vumiapi.batch_start([tag])

        for i in range(100, 125):
            from_addr = "+%s%s" % (i, tag[1][-5:])
            msg = self.mkmsg_in('hello', to_addr=to_addr, from_addr=from_addr,
                                    message_id='msg-%s' % (i,))

            TaggingMiddleware.add_tag_to_msg(msg, tag)
            self.vumiapi.mdb.add_inbound_message(msg, tag=tag)
            yield self.dispatch(msg)

        replies = self.vumiapi.batch_replies(batch_id)
        self.assertTrue(len(replies), 100)
        self.assertTrue(all(reply['content'] == 'hello' for reply in replies))
        self.assertTrue(all(reply['from_addr'].endswith(tag[1][-5:]) for
                                reply in replies))


    @inlineCallbacks
    def test_consume_ack(self):
        ack_event = yield self.publish_event(user_message_id='123',
                                             event_type='ack',
                                             sent_message_id='xyz')
        [event_id] = self.app.store.message_events('123')
        self.assertEqual(self.app.store.get_event(event_id), ack_event)

    @inlineCallbacks
    def test_consume_delivery_report(self):
        dr_event = yield self.publish_event(user_message_id='123',
                                            event_type='delivery_report',
                                            delivery_status='delivered')
        [event_id] = self.app.store.message_events('123')
        self.assertEqual(self.app.store.get_event(event_id), dr_event)

    @inlineCallbacks
    def test_consume_user_message(self):
        msg = self.mkmsg_in()
        yield self.dispatch(msg)
        self.assertEqual(self.app.store.get_inbound_message(msg['message_id']),
                         msg)

    @inlineCallbacks
    def test_close_session(self):
        msg = self.mkmsg_in(session_event=TransportUserMessage.SESSION_CLOSE)
        yield self.dispatch(msg)
        self.assertEqual(self.app.store.get_inbound_message(msg['message_id']),
                         msg)
