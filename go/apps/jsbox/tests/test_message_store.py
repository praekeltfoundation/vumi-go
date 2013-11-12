# -*- coding: utf-8 -*-

from mock import Mock, patch

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.message_store import MessageStoreResource
from go.vumitools.tests.utils import GoAppWorkerTestMixin
from go.vumitools.account import AccountStore
from go.vumitools.tests.helpers import GoMessageHelper


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.user_api = Mock()

    def user_api_for_api(self, api):
        return self.user_api


class MessageStoreResourceTestCase(ResourceTestCaseBase, GoAppWorkerTestMixin):
    use_riak = True
    app_worker_cls = StubbedAppWorker
    resource_cls = MessageStoreResource

    @inlineCallbacks
    def setUp(self):
        super(MessageStoreResourceTestCase, self).setUp()
        yield self._persist_setUp()

        self.msg_helper = GoMessageHelper()
        self.vumi_api = yield self.get_vumi_api()
        self.message_store = self.vumi_api.mdb
        yield self.setup_user_api(self.vumi_api)

        self.conversation = yield self.create_conversation(started=True)

        # monkey patch for testing!
        self.app_worker.conversation_for_api = lambda *a: self.conversation

        yield self.create_resource({})

    def _worker_name(self):
        """hack to get GoAppWorkerTestMixin to get a `conversation_type` when
        calling `create_conversation()`"""
        return 'unnamed'

    def tearDown(self):
        super(MessageStoreResourceTestCase, self).tearDown()
        return self._persist_tearDown()

    @inlineCallbacks
    def test_handle_progress_status(self):
        reply = yield self.dispatch_command('progress_status')
        self.assertTrue(reply['success'])
        self.assertTrue(isinstance(reply['progress_status'], dict))

    @inlineCallbacks
    def test_handle_count_replies(self):
        reply = yield self.dispatch_command('count_replies')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 0)

    @inlineCallbacks
    def test_handle_count_sent_messages(self):
        reply = yield self.dispatch_command('count_sent_messages')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 0)

    @inlineCallbacks
    def test_handle_count_inbound_uniques(self):
        reply = yield self.dispatch_command('count_inbound_uniques')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 0)

    @inlineCallbacks
    def test_handle_count_outbound_uniques(self):
        reply = yield self.dispatch_command('count_outbound_uniques')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 0)

    @inlineCallbacks
    def test_handle_inbound_throughput(self):
        reply = yield self.dispatch_command('inbound_throughput',
                                            sample_time=1)
        self.assertTrue(reply['success'])
        self.assertEqual(reply['throughput'], 0)

    @inlineCallbacks
    def test_handle_outbound_throughput(self):
        reply = yield self.dispatch_command('outbound_throughput',
                                            sample_time=1)
        self.assertTrue(reply['success'])
        self.assertEqual(reply['throughput'], 0)
