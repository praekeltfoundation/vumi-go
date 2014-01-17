# -*- coding: utf-8 -*-

"""Tests for go.apps.opt_out application"""

import json

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.apps.opt_out.vumi_app import OptOutApplication
from go.apps.tests.helpers import AppWorkerHelper
from go.vumitools.opt_out import OptOutStore


class TestOptOutApplication(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(AppWorkerHelper(OptOutApplication))
        self.app = yield self.app_helper.get_app_worker({})

        conv = yield self.app_helper.create_conversation()
        yield self.app_helper.start_conversation(conv)
        self.conversation = yield self.app_helper.get_conversation(conv.key)

        vumi_api = self.app_helper.vumi_helper.get_vumi_api()
        self.opt_out_store = OptOutStore(
            vumi_api.manager, self.conversation.user_account.key)

    @inlineCallbacks
    def test_sms_opt_out(self):
        yield self.app_helper.make_dispatch_inbound(
            "STOP", from_addr="12345", to_addr="666", conv=self.conversation)
        [msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(msg.get('content'), "You have opted out")
        opt_out = yield self.opt_out_store.get_opt_out("msisdn", "12345")
        self.assertNotEqual(opt_out, None)

    @inlineCallbacks
    def test_sms_opt_out_no_account(self):
        yield self.app_helper.make_dispatch_inbound(
            "STOP", from_addr="12345", to_addr="666")
        [msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(msg.get('content'),
                         "Your opt-out was received but we failed to link it "
                         "to a specific service, please try again later.")

    @inlineCallbacks
    def test_http_opt_out(self):
        yield self.app_helper.make_dispatch_inbound(
            "STOP", from_addr="12345", to_addr="666", conv=self.conversation,
            transport_type="http_api")
        [msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(json.loads(msg['content']), {
            "msisdn": "12345",
            "opted_in": False,
        })
        opt_out = yield self.opt_out_store.get_opt_out("msisdn", "12345")
        self.assertNotEqual(opt_out, None)
