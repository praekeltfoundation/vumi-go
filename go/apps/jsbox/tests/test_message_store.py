# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from vxsandbox.tests.utils import DummyAppWorker
from vxsandbox.resources.tests.utils import ResourceTestCaseBase

from go.apps.jsbox.message_store import MessageStoreResource
from go.vumitools.tests.helpers import GoMessageHelper, VumiApiHelper


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.user_api = None

    def user_api_for_api(self, api):
        return self.user_api


class TestMessageStoreResource(ResourceTestCaseBase):
    app_worker_cls = StubbedAppWorker
    resource_cls = MessageStoreResource

    @inlineCallbacks
    def setUp(self):
        super(TestMessageStoreResource, self).setUp()

        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.msg_helper = self.add_helper(GoMessageHelper())
        self.user_helper = yield self.vumi_helper.make_user(u"user")
        self.app_worker.user_api = self.user_helper.user_api

        opms = self.vumi_helper.get_vumi_api().get_operational_message_store()

        self.conversation = yield self.user_helper.create_conversation(
            u'jsbox', started=True)

        # store inbound
        yield opms.add_inbound_message(
            self.msg_helper.make_inbound('hello'),
            batch_ids=[self.conversation.batch.key])

        # store outbound
        outbound_msg = self.msg_helper.make_outbound('hello')
        yield opms.add_outbound_message(
            outbound_msg, batch_ids=[self.conversation.batch.key])

        # ack outbound
        event = self.msg_helper.make_ack(outbound_msg)
        yield opms.add_event(event)

        # monkey patch for when no conversation_key is provided
        self.app_worker.conversation_for_api = lambda *a: self.conversation

        yield self.create_resource({})

    @inlineCallbacks
    def test_handle_progress_status(self):
        reply = yield self.dispatch_command('progress_status')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['progress_status'], {
            'ack': 1,
            'delivery_report': 0,
            'delivery_report_delivered': 0,
            'delivery_report_failed': 0,
            'delivery_report_pending': 0,
            'nack': 0,
            'sent': 1,
        })

    @inlineCallbacks
    def test_handle_count_replies(self):
        reply = yield self.dispatch_command('count_replies')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 1)

    @inlineCallbacks
    def test_handle_count_sent_messages(self):
        reply = yield self.dispatch_command('count_sent_messages')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 1)

    @inlineCallbacks
    def test_handle_count_inbound_uniques(self):
        reply = yield self.dispatch_command('count_inbound_uniques')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 1)

    @inlineCallbacks
    def test_handle_count_outbound_uniques(self):
        reply = yield self.dispatch_command('count_outbound_uniques')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 1)

    @inlineCallbacks
    def test_handle_inbound_throughput(self):
        reply = yield self.dispatch_command('inbound_throughput',
                                            sample_time=60)
        self.assertTrue(reply['success'])
        self.assertEqual(reply['throughput'], 1)

    @inlineCallbacks
    def test_handle_outbound_throughput(self):
        reply = yield self.dispatch_command('outbound_throughput',
                                            sample_time=60)
        self.assertTrue(reply['success'])
        self.assertEqual(reply['throughput'], 1)

    @inlineCallbacks
    def test_invalid_conversation_key(self):
        reply = yield self.dispatch_command('progress_status',
                                            conversation_key='foo')
        self.assertFalse(reply['success'])
        self.assertEqual(reply['reason'], 'Invalid conversation_key')
