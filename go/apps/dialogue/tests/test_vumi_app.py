# -*- coding: utf-8 -*-

"""Tests for go.apps.dialogue.vumi_app"""

import pkg_resources

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.trial.unittest import SkipTest

from vumi.tests.utils import LogCatcher

from go.apps.dialogue.vumi_app import DialogueApplication
from go.apps.dialogue.tests.dummy_polls import simple_poll
from go.vumitools.tests.utils import AppWorkerTestCase


class DialogueApplicationTestCase(AppWorkerTestCase):

    application_class = DialogueApplication
    transport_type = u'sms'

    @inlineCallbacks
    def setUp(self):
        yield super(DialogueApplicationTestCase, self).setUp()
        if DialogueApplication.find_nodejs() is None:
            raise SkipTest("No node.js executable found.")

        sandboxer_js = pkg_resources.resource_filename('vumi.application',
                                                       'sandboxer.js')
        redis = yield self.get_redis_manager()
        self.kv_redis = redis.sub_manager('kv')
        config = self.mk_config({
            'args': [sandboxer_js],
            'timeout': 10,
            'app_context': (
                "{require: function(m) { if (m == 'jed' || m == 'vumigo_v01')"
                " return require(m); return null; }, Buffer: Buffer}"
            ),
            'sandbox': {
                'config': {
                    'cls': 'go.apps.dialogue.vumi_app.PollConfigResource',
                },
                'contacts': {
                    'cls': 'go.apps.jsbox.contacts.ContactsResource',
                },
                'kv': {
                    'cls': 'vumi.application.sandbox.RedisResource',
                    'redis_manager': {'FAKE_REDIS': self.kv_redis},
                },
                'outbound': {
                    'cls': 'go.apps.jsbox.outbound.GoOutboundResource',
                },
            },
        })
        self.app = yield self.get_application(config)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!
        self.message_store = self.vumi_api.mdb

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)

        yield self.setup_tagpools()

    @inlineCallbacks
    def setup_conversation(self, contact_count=2,
                           from_addr=u'+27831234567{0}',
                           config={}):
        config["poll"] = simple_poll

        user_api = self.user_api
        group = yield user_api.contact_store.new_group(u'test group')

        for i in range(contact_count):
            yield user_api.contact_store.new_contact(
                name=u'First', surname=u'Surname %s' % (i,),
                msisdn=from_addr.format(i), groups=[group])

        conversation = yield self.create_conversation(
            delivery_class=u'sms', config=config)
        conversation.add_group(group)
        conversation.set_status_started()
        yield conversation.save()
        returnValue(conversation)

    @inlineCallbacks
    def send_send_dialogue_command(self, conversation):
        batch_id = yield conversation.get_latest_batch_key()
        yield self.dispatch_command(
            "send_dialogue",
            user_account_key=self.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            delivery_class=conversation.delivery_class,
        )

    @inlineCallbacks
    def test_send_dialogue_command(self):
        conv = yield self.setup_conversation()
        with LogCatcher(message='Switched to state:') as lc:
            yield self.send_send_dialogue_command(conv)
            self.assertEqual(lc.messages(),
                             ['Switched to state: choice-1'] * 2)
        [msg1, msg2] = msgs = yield self.get_dispatched_outbound()
        for msg in msgs:
            self.assertEqual(msg["content"],
                             "What is your favourite colour?\n1. Red\n2. Blue")
            go_metadata = msg["helper_metadata"]["go"]
            self.assertEqual(go_metadata["conversation_type"], "dialogue")
            self.assertEqual(go_metadata["conversation_key"], conv.key)
        self.assertEqual(sorted([m["to_addr"] for m in msgs]),
                         ["+278312345670", "+278312345671"])

    @inlineCallbacks
    def test_user_message(self):
        conversation = yield self.setup_conversation()
        yield self.start_conversation(conversation)
        msg = self.mkmsg_in()
        yield self.dispatch_to_conv(msg, conversation)
        [reply] = yield self.get_dispatched_outbound()
        self.assertEqual(reply["content"],
                         "What is your favourite colour?\n1. Red\n2. Blue")

    @inlineCallbacks
    def test_event(self):
        conversation = yield self.setup_conversation()
        yield self.start_conversation(conversation)
        msg = self.mkmsg_in()
        conversation.set_go_helper_metadata(msg['helper_metadata'])
        yield self.store_outbound_msg(msg, conversation)
        event = self.mkmsg_ack(user_message_id=msg['message_id'])
        conversation.set_go_helper_metadata(event['helper_metadata'])
        with LogCatcher(message="Saw") as lc:
            yield self.dispatch_event(event)
            self.assertEqual(lc.messages(),
                             ['Saw ack for message abc.'])
