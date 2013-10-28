# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.static_reply.vumi_app import StaticReplyApplication
from go.vumitools.tests.helpers import GoMessageHelper


class TestStaticReplyApplication(AppWorkerTestCase):
    application_class = StaticReplyApplication

    @inlineCallbacks
    def setUp(self):
        super(TestStaticReplyApplication, self).setUp()
        self.config = self.mk_config({})
        self.app = yield self.get_application(self.config)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)
        self.msg_helper = GoMessageHelper(self.user_api.api.mdb)

    @inlineCallbacks
    def test_receive_message(self):
        conv = yield self.create_conversation(config={
            'reply_text': 'Your message is important to us.',
        }, started=True)
        yield self.dispatch_to_conv(self.msg_helper.make_inbound("foo"), conv)
        [reply] = yield self.get_dispatched_messages()
        self.assertEqual('Your message is important to us.', reply['content'])
        self.assertEqual(u'close', reply['session_event'])

    @inlineCallbacks
    def test_receive_message_no_reply(self):
        conv = yield self.create_conversation(config={}, started=True)
        yield self.dispatch_to_conv(self.msg_helper.make_inbound("foo"), conv)
        self.assertEqual([], (yield self.get_dispatched_messages()))
