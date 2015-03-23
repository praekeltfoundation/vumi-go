# -*- coding: utf-8 -*-
import json
import pkg_resources

import mock

from twisted.internet.defer import inlineCallbacks

from vxsandbox import JsSandbox
from vxsandbox.resources import SandboxCommand

from vumi.application.tests.helpers import find_nodejs_or_skip_test
from vumi.middleware.tagger import TaggingMiddleware
from vumi.tests.helpers import VumiTestCase
from vumi.tests.utils import LogCatcher

from go.apps.jsbox.vumi_app import JsBoxApplication, ConversationConfigResource
from go.apps.tests.helpers import AppWorkerHelper


class TestJsBoxApplication(VumiTestCase):
    APPS = {
        'success': """
            api.%(method)s = function(command) {
                this.log_info("From command: inbound-message",
                    function (reply) {
                        this.log_info("Log successful: " + reply.success);
                        this.done();
                    }
                );
            }
        """,

        'cmd': """
            api.%(method)s = function(command) {
                this.log_info(JSON.stringify(command));
                this.done();
            }
        """
    }

    @inlineCallbacks
    def setUp(self):
        nodejs_executable = find_nodejs_or_skip_test(JsSandbox)
        sandboxer_js = pkg_resources.resource_filename('vumi.application',
                                                       'sandboxer.js')
        self.app_helper = self.add_helper(AppWorkerHelper(JsBoxApplication))
        self.app = yield self.app_helper.get_app_worker({
            'executable': nodejs_executable,
            'args': [sandboxer_js],
            'timeout': 10,
        })

    def setup_conversation(self, config=None, **kw):
        return self.app_helper.create_conversation(
            config=(config or {}), **kw)

    def set_conversation_tag(self, msg, conversation):
        # TOOD: Move into AppWorkerTestCase once it's working
        tag = (conversation.delivery_tag_pool, conversation.delivery_tag)
        TaggingMiddleware.add_tag_to_msg(msg, tag)
        return msg

    def mk_conv_config(self, app=None, delivery_class=None, **js_config):
        if delivery_class is not None:
            js_config['delivery_class'] = delivery_class

        if app is None:
            app = self.APPS['success'] % {'method': 'on_inbound_message'}

        config = {
            'jsbox': {'javascript': app},
            'jsbox_app_config': {
                'config': {
                    'key': 'config',
                    'value': json.dumps(js_config)
                }
            },
        }

        return config

    def mk_dummy_api(self, conversation):
        dummy_api = mock.Mock()
        dummy_api.config = self.app.get_config_for_conversation(conversation)
        return dummy_api

    @inlineCallbacks
    def test_start(self):
        conversation = yield self.setup_conversation()
        with LogCatcher() as lc:
            yield self.app_helper.start_conversation(conversation)
            self.assertTrue("Starting javascript sandbox conversation "
                            "(key: u'%s')." % conversation.key
                            in lc.messages())

    def send_send_jsbox_command(self, conversation):
        return self.app_helper.dispatch_command(
            "send_jsbox",
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key)

    @inlineCallbacks
    def test_send_jsbox_command(self):
        group = yield self.app_helper.create_group(u'group')
        contact1 = yield self.app_helper.create_contact(
            msisdn=u'+271',
            name=u'a',
            surname=u'a',
            groups=[group])
        contact2 = yield self.app_helper.create_contact(
            msisdn=u'+272',
            name=u'b',
            surname=u'b',
            groups=[group])

        config = self.mk_conv_config(
            app=self.APPS['cmd'] % {'method': 'on_inbound_message'})
        conv = yield self.setup_conversation(config=config, groups=[group])
        yield self.app_helper.start_conversation(conv)

        with LogCatcher(message='msg') as lc:
            yield self.send_send_jsbox_command(conv)
            [msg1, msg2] = sorted(
                [json.loads(m).get('msg') for m in lc.messages()],
                key=lambda msg: msg['from_addr'])

        self.assertEqual(msg1['from_addr'], contact1.msisdn)
        self.assertEqual(msg2['from_addr'], contact2.msisdn)

        msgs = self.app_helper.get_dispatched_outbound()
        self.assertEqual(msgs, [])

    @inlineCallbacks
    def test_send_jsbox_command_configured_delivery_class(self):
        group = yield self.app_helper.create_group(u'group')
        contact1 = yield self.app_helper.create_contact(
            msisdn=u'+271',
            twitter_handle=u'@a',
            name=u'a',
            surname=u'a',
            groups=[group])
        contact2 = yield self.app_helper.create_contact(
            msisdn=u'+272',
            twitter_handle=u'@b',
            name=u'b',
            surname=u'b',
            groups=[group])

        config = self.mk_conv_config(
            app=self.APPS['cmd'] % {'method': 'on_inbound_message'},
            delivery_class='twitter')
        conv = yield self.setup_conversation(config=config, groups=[group])
        yield self.app_helper.start_conversation(conv)

        with LogCatcher(message='msg') as lc:
            yield self.send_send_jsbox_command(conv)
            [msg1, msg2] = sorted(
                [json.loads(m).get('msg') for m in lc.messages()],
                key=lambda msg: msg['from_addr'])

        self.assertEqual(msg1['from_addr'], contact1.twitter_handle)
        self.assertEqual(msg2['from_addr'], contact2.twitter_handle)

    @inlineCallbacks
    def test_send_jsbox_command_bad_config(self):
        group = yield self.app_helper.create_group(u'group')

        config = self.mk_conv_config(
            app=self.APPS['cmd'] % {'method': 'on_inbound_message'},
            delivery_class='twitter')
        config['jsbox_app_config']['config']['value'] = 'bad'

        conv = yield self.setup_conversation(config=config, groups=[group])
        yield self.app_helper.start_conversation(conv)

        with LogCatcher() as lc:
            yield self.send_send_jsbox_command(conv)

            self.assertTrue(any(
                "Bad jsbox js config: bad" in
                e['message'][0] for e in lc.errors))

    @inlineCallbacks
    def test_user_message(self):
        conv = yield self.setup_conversation(config=self.mk_conv_config())
        yield self.app_helper.start_conversation(conv)
        with LogCatcher(message="Log successful") as lc:
            yield self.app_helper.make_dispatch_inbound("inbound", conv=conv)
        self.assertEqual(lc.messages(), ["Log successful: true"])

    @inlineCallbacks
    def test_user_message_no_javascript(self):
        conv = yield self.setup_conversation(config={})
        yield self.app_helper.start_conversation(conv)
        with LogCatcher() as lc:
            yield self.app_helper.make_dispatch_inbound("inbound", conv=conv)
            self.assertTrue("No JS for conversation: %s" % (conv.key,)
                            in lc.messages())

    @inlineCallbacks
    def test_user_message_sandbox_id(self):
        conversation = yield self.setup_conversation(
            config=self.mk_conv_config())
        yield self.app_helper.start_conversation(conversation)
        msg = self.app_helper.make_inbound("inbound", conv=conversation)
        config = yield self.app.get_config(msg)
        self.assertEqual(config.sandbox_id, conversation.user_account.key)

    def test_delivery_class_inference(self):
        def check_inference_for(transport_type, expected_delivery_class):
            msg = self.app_helper.make_inbound(
                "inbound", transport_type=transport_type)
            self.assertEqual(
                self.app.infer_delivery_class(msg),
                expected_delivery_class)

        check_inference_for(None, 'sms')
        check_inference_for('smpp', 'sms')
        check_inference_for('sms', 'sms')
        check_inference_for('ussd', 'ussd')
        check_inference_for('twitter', 'twitter')
        check_inference_for('xmpp', 'gtalk')
        check_inference_for('wechat', 'wechat')
        check_inference_for('mxit', 'mxit')

    @inlineCallbacks
    def test_event_not_in_sandbox(self):
        app = self.APPS['success'] % {'method': 'on_inbound_event'}
        conversation = yield self.setup_conversation(
            config=self.mk_conv_config(app=app))
        yield self.app_helper.start_conversation(conversation)
        msg = yield self.app_helper.make_stored_outbound(
            conversation, "outbound")
        with LogCatcher() as lc:
            yield self.app_helper.make_dispatch_ack(msg, conv=conversation)
        self.assertFalse("Log successful: true" in lc.messages())
        self.assertTrue(
            "Ignoring event for conversation: %s" % (conversation.key,)
            in lc.messages())

    @inlineCallbacks
    def test_event_in_sandbox(self):
        app = self.APPS['success'] % {'method': 'on_inbound_event'}
        conversation = yield self.setup_conversation(
            config=self.mk_conv_config(app=app, process_events=True))
        yield self.app_helper.start_conversation(conversation)
        msg = yield self.app_helper.make_stored_outbound(
            conversation, "outbound")
        with LogCatcher() as lc:
            yield self.app_helper.make_dispatch_ack(msg, conv=conversation)
        self.assertTrue("Log successful: true" in lc.messages())
        self.assertFalse(
            "Ignoring event for conversation: %s" % (conversation.key,)
            in lc.messages())

    @inlineCallbacks
    def test_conversation_for_api(self):
        conversation = yield self.setup_conversation()
        conversation.set_status_started()
        dummy_api = self.mk_dummy_api(conversation)
        self.assertEqual(self.app.conversation_for_api(dummy_api),
                         conversation)

    @inlineCallbacks
    def test_user_api_for_api(self):
        conversation = yield self.setup_conversation()
        conversation.set_status_started()
        dummy_api = self.mk_dummy_api(conversation)
        user_api = self.app.user_api_for_api(dummy_api)
        self.assertEqual(user_api.user_account_key,
                         conversation.user_account.key)

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

        [msg] = yield self.app_helper.get_dispatched_outbound()
        self.assertEqual(msg.payload['to_addr'], "123456")
        self.assertEqual(msg.payload['from_addr'], "666666")
        self.assertEqual(msg.payload['content'], "hello world")
        self.assertEqual(msg.payload['transport_name'], "sphex_transport")
        self.assertEqual(msg.payload['transport_type'], "sphex")
        self.assertEqual(msg.payload['message_type'], "user_message")
        self.assertEqual(msg.payload['helper_metadata']['go'], {
            'user_account': conversation.user_account.key,
            'conversation_type': conversation.conversation_type,
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


class TestConversationConfigResource(VumiTestCase):
    def setUp(self):
        self.conversation = mock.Mock()
        self.app_worker = mock.Mock()
        self.dummy_api = object()
        self.resource = ConversationConfigResource("test", self.app_worker, {})
        self.app_worker.conversation_for_api = mock.Mock(
            return_value=self.conversation)

    def set_app_config(self, key_values):
        app_config = dict((k, {"value": v}) for k, v
                          in key_values.iteritems())
        self.conversation.config = {
            "jsbox_app_config": app_config,
        }

    def check_reply(self, reply, cmd, value):
        self.assertEqual(reply['reply'], True)
        self.assertEqual(reply['cmd_id'], cmd['cmd_id'])
        self.assertEqual(reply['value'], value)

    def test_present_key(self):
        cmd = SandboxCommand(key="foo")
        self.set_app_config({"foo": "foo value"})
        reply = self.resource.handle_get(self.dummy_api, cmd)
        self.check_reply(reply, cmd, "foo value")

    def test_missing_key(self):
        cmd = SandboxCommand(key="foo")
        self.set_app_config({})
        reply = self.resource.handle_get(self.dummy_api, cmd)
        self.check_reply(reply, cmd, None)

    def test_with_app_config_absent(self):
        cmd = SandboxCommand(key="foo")
        self.conversation.config = {"jsbox": {}}
        reply = self.resource.handle_get(self.dummy_api, cmd)
        self.check_reply(reply, cmd, None)
