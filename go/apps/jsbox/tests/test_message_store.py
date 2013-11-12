# -*- coding: utf-8 -*-

from mock import Mock

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.message_store import MessageStoreResource
from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.account import AccountStore
from go.vumitools.tests.helpers import GoMessageHelper


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.user_api = Mock()

    def user_api_for_api(self, api):
        return self.user_api


class MessageStoreResourceTestCase(ResourceTestCaseBase, GoPersistenceMixin):
    use_riak = True
    app_worker_cls = StubbedAppWorker
    resource_cls = MessageStoreResource

    # get_progress_status
    # count_replies
    # count_sent_messages
    # count_inbound_uniques
    # count_outbound_uniques
    # get_aggregate_keys
    # get_inbound_throughput
    # get_outbound_throughput

    @inlineCallbacks
    def setUp(self):
        super(MessageStoreResourceTestCase, self).setUp()
        yield self._persist_setUp()

        self.msg_helper = GoMessageHelper()

        # We pass `self` in as the VumiApi object here, because mk_user() just
        # grabs .account_store off it.
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        self.account = yield self.mk_user(self, u'user')

        yield self.create_resource({})
        print self.create_conversation

    def tearDown(self):
        super(MessageStoreResourceTestCase, self).tearDown()
        return self._persist_tearDown()

    @inlineCallbacks
    def test_handle_progress_status(self):
        reply = yield self.dispatch_command('progress_status')

        self.assertTrue(reply['success'])
        self.assertEqual(reply['progress_status'], {})
