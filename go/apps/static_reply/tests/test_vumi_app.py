# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.apps.static_reply.vumi_app import StaticReplyApplication
from go.apps.tests.helpers import AppWorkerHelper


class TestStaticReplyApplication(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(
            AppWorkerHelper(StaticReplyApplication))
        self.app = yield self.app_helper.get_app_worker({})

    @inlineCallbacks
    def test_receive_message(self):
        conv = yield self.app_helper.create_conversation(config={
            'reply_text': 'Your message is important to us.',
        }, started=True)
        yield self.app_helper.make_dispatch_inbound("foo", conv=conv)
        [reply] = yield self.app_helper.get_dispatched_outbound()
        self.assertEqual('Your message is important to us.', reply['content'])
        self.assertEqual(u'close', reply['session_event'])

    @inlineCallbacks
    def test_receive_message_no_reply(self):
        conv = yield self.app_helper.create_conversation(started=True)
        yield self.app_helper.make_dispatch_inbound("foo", conv=conv)
        self.assertEqual([], self.app_helper.get_dispatched_outbound())
