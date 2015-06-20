# -*- coding: utf-8 -*-

"""Tests for go.apps.dialogue.vumi_app"""

import os
import json
import pkg_resources

from twisted.internet.defer import inlineCallbacks, returnValue

from vxsandbox.utils import find_nodejs_or_skip_test
from vxsandbox.tests.utils import DummyAppWorker
from vxsandbox.resources.tests.utils import ResourceTestCaseBase

from vumi.tests.helpers import VumiTestCase
from vumi.tests.utils import LogCatcher

from go.apps.dialogue.vumi_app import DialogueApplication, PollConfigResource
from go.apps.dialogue.utils import dialogue_js_config
from go.apps.dialogue.tests.dummy_polls import simple_poll
from go.apps.tests.helpers import AppWorkerHelper


class DummyDialogueAppWorker(DummyAppWorker):
    def __init__(self):
        super(DummyDialogueAppWorker, self).__init__()
        self.conv = None

    def conversation_for_api(self, api):
        return self.conv


class TestDialogueApplication(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        nodejs_executable = find_nodejs_or_skip_test(DialogueApplication)

        self.app_helper = self.add_helper(AppWorkerHelper(DialogueApplication))

        sandboxer_js = pkg_resources.resource_filename('vumi.application',
                                                       'sandboxer.js')
        node_path = os.environ['SANDBOX_NODE_PATH']  # Required to run tests.
        redis = yield self.app_helper.vumi_helper.get_redis_manager()
        self.kv_redis = redis.sub_manager('kv')
        self.app = yield self.app_helper.get_app_worker({
            'executable': nodejs_executable,
            'args': [sandboxer_js],
            'timeout': 10,
            'app_context': (
                "{require: function(m) {"
                " if (['moment', 'url', 'querystring', 'crypto', 'lodash',"
                " 'q', 'jed', 'libxmljs', 'zlib', 'vumigo_v01', 'vumigo_v02'"
                "].indexOf(m) >= 0) return require(m); return null;"
                " }, Buffer: Buffer}"
            ),
            'env': {
                'NODE_PATH': node_path,
            },
            'sandbox': {
                'config': {
                    'cls': 'go.apps.dialogue.vumi_app.PollConfigResource',
                },
                'contacts': {
                    'cls': 'go.apps.jsbox.contacts.ContactsResource',
                },
                'kv': {
                    'cls': 'vxsandbox.RedisResource',
                    'redis_manager': {'FAKE_REDIS': self.kv_redis},
                },
                'outbound': {
                    'cls': 'go.apps.jsbox.outbound.GoOutboundResource',
                },
            },
            'rlimits': {
                'RLIMIT_STACK': [2 * 1024 * 1024] * 2,
                'RLIMIT_AS': [256 * 1024 * 1024] * 2,
            },
        })

    @inlineCallbacks
    def setup_conversation(self, poll=None):
        group = yield self.app_helper.create_group(u'group')

        yield self.app_helper.create_contact(
            msisdn=u'+278312345670',
            twitter_handle=u'@0',
            groups=[group],
            name=u'Contact',
            surname=u'0')

        yield self.app_helper.create_contact(
            msisdn=u'+278312345671',
            twitter_handle=u'@1',
            groups=[group],
            name=u'Contact',
            surname=u'1')

        config = {"poll": poll or simple_poll()}
        conv = yield self.app_helper.create_conversation(
            config=config, groups=[group])
        returnValue(conv)

    def send_send_jsbox_command(self, conversation):
        return self.app_helper.dispatch_command(
            "send_jsbox",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key,
        )

    @inlineCallbacks
    def test_send_dialogue_command(self):
        conv = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conv)
        with LogCatcher(message='Switched to state:') as lc:
            yield self.send_send_jsbox_command(conv)
            self.assertEqual(lc.messages(),
                             ['Switched to state: choice-1'] * 2)
        msgs = self.app_helper.get_dispatched_outbound()
        for msg in msgs:
            self.assertEqual(msg["content"],
                             "What is your favourite colour?\n1. Red\n2. Blue")
            self.assertEqual(msg["in_reply_to"], None)
            go_metadata = msg["helper_metadata"]["go"]
            self.assertEqual(go_metadata["conversation_type"], "dialogue")
            self.assertEqual(go_metadata["conversation_key"], conv.key)
        self.assertEqual(sorted([m["to_addr"] for m in msgs]),
                         ["+278312345670", "+278312345671"])

    @inlineCallbacks
    def test_send_dialogue_command_delivery_class(self):
        poll = simple_poll()
        poll['poll_metadata']['delivery_class'] = 'twitter'
        conv = yield self.setup_conversation(poll=poll)
        yield self.app_helper.start_conversation(conv)
        with LogCatcher(message='Switched to state:') as lc:
            yield self.send_send_jsbox_command(conv)
            self.assertEqual(lc.messages(),
                             ['Switched to state: choice-1'] * 2)
        msgs = self.app_helper.get_dispatched_outbound()
        for msg in msgs:
            self.assertEqual(msg["content"],
                             "What is your favourite colour?\n1. Red\n2. Blue")
            self.assertEqual(msg["in_reply_to"], None)
            go_metadata = msg["helper_metadata"]["go"]
            self.assertEqual(go_metadata["conversation_type"], "dialogue")
            self.assertEqual(go_metadata["conversation_key"], conv.key)
        self.assertEqual(sorted([m["to_addr"] for m in msgs]),
                         ["@0", "@1"])

    @inlineCallbacks
    def test_user_message(self):
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        with LogCatcher(message='Switched to state:') as lc:
            yield self.app_helper.make_dispatch_inbound(
                "hello", conv=conversation)
            self.assertEqual(lc.messages(),
                             ['Switched to state: choice-1'])
        [reply] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(reply["content"],
                         "What is your favourite colour?\n1. Red\n2. Blue")

    @inlineCallbacks
    def test_ack(self):
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        msg = yield self.app_helper.make_stored_outbound(
            conversation, "foo")
        with LogCatcher(message="Ignoring") as lc:
            yield self.app_helper.make_dispatch_ack(msg, conv=conversation)
        self.assertEqual(
            lc.messages(),
            ["Ignoring event for conversation: %s" % (conversation.key,)])

    @inlineCallbacks
    def test_delivery_report(self):
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        msg = yield self.app_helper.make_stored_outbound(
            conversation, "foo")
        with LogCatcher(message="Ignoring") as lc:
            yield self.app_helper.make_dispatch_delivery_report(
                msg, conv=conversation)
        self.assertEqual(
            lc.messages(),
            ["Ignoring event for conversation: %s" % (conversation.key,)])

    @inlineCallbacks
    def test_send_message_command(self):
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        msg_options = {
            'transport_name': 'sphex_transport',
            'from_addr': '666666',
            'transport_type': 'sphex',
            'helper_metadata': {'foo': {'bar': 'baz'}},
        }
        yield self.app_helper.dispatch_command(
            "send_message",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            command_data={
                "batch_id": conversation.batch.key,
                "to_addr": "123456",
                "content": "hello world",
                "msg_options": msg_options,
            })

        [msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(msg.payload['to_addr'], "123456")
        self.assertEqual(msg.payload['from_addr'], "666666")
        self.assertEqual(msg.payload['content'], "hello world")
        self.assertEqual(msg.payload['transport_name'], "sphex_transport")
        self.assertEqual(msg.payload['transport_type'], "sphex")
        self.assertEqual(msg.payload['message_type'], "user_message")
        self.assertEqual(msg.payload['helper_metadata']['go'], {
            'user_account': conversation.user_account.key,
            'conversation_type': 'dialogue',
            'conversation_key': conversation.key,
        })
        self.assertEqual(msg.payload['helper_metadata']['foo'],
                         {'bar': 'baz'})

    @inlineCallbacks
    def test_process_command_send_message_in_reply_to(self):
        conversation = yield self.setup_conversation()
        yield self.app_helper.start_conversation(conversation)
        msg = yield self.app_helper.make_stored_inbound(conversation, "foo")
        yield self.app_helper.dispatch_command(
            "send_message",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            command_data={
                "batch_id": conversation.batch.key,
                "to_addr": "to_addr",
                "content": "foo",
                u'msg_options': {
                    u'transport_name': u'smpp_transport',
                    u'in_reply_to': msg['message_id'],
                    u'transport_type': u'sms',
                    u'from_addr': u'default10080',
                },
            })
        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], msg['from_addr'])
        self.assertEqual(sent_msg['content'], 'foo')
        self.assertEqual(sent_msg['in_reply_to'], msg['message_id'])


class TestPollConfigResource(ResourceTestCaseBase):
    # TODO: Make this resource stuff into a helper in vumi.
    app_worker_cls = DummyDialogueAppWorker
    resource_cls = PollConfigResource

    @inlineCallbacks
    def setUp(self):
        super(TestPollConfigResource, self).setUp()
        self.app_helper = self.add_helper(AppWorkerHelper(DialogueApplication))
        self.app = yield self.app_helper.get_app_worker({})
        yield self.create_resource({})

    @inlineCallbacks
    def test_get(self):
        conv = yield self.app_helper.create_conversation(
            config={'poll': simple_poll()})
        self.app_worker.conv = conv

        reply = yield self.dispatch_command('get', key='config')
        config = json.loads(reply['value'])

        self.assertEqual(config, dialogue_js_config(conv))
