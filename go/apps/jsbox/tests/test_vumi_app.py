# -*- coding: utf-8 -*-
import pkg_resources

import mock

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.trial.unittest import SkipTest, TestCase

from go.vumitools.tests.utils import AppWorkerTestCase

from go.apps.jsbox.vumi_app import JsBoxApplication, ConversationConfigResource

from vumi.application.sandbox import JsSandbox, SandboxCommand
from vumi.middleware.tagger import TaggingMiddleware
from vumi.tests.utils import LogCatcher


class JsBoxApplicationTestCase(AppWorkerTestCase):

    use_riak = True
    application_class = JsBoxApplication

    @inlineCallbacks
    def setUp(self):
        yield super(JsBoxApplicationTestCase, self).setUp()
        if JsSandbox.find_nodejs() is None:
            raise SkipTest("No node.js executable found.")

        sandboxer_js = pkg_resources.resource_filename('vumi.application',
                                                       'sandboxer.js')
        self.config = self.mk_config({
            'args': [sandboxer_js],
            'timeout': 10,
        })
        self.app = yield self.get_application(self.config)

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
                           config={}, started=False):
        user_api = self.user_api
        group = yield user_api.contact_store.new_group(u'test group')

        for i in range(contact_count):
            yield user_api.contact_store.new_contact(
                name=u'First', surname=u'Surname %s' % (i,),
                msisdn=from_addr.format(i), groups=[group])

        conversation = yield self.create_conversation(
            delivery_tag_pool=u'pool', delivery_class=u'sms',
            delivery_tag=u'tag1', config=config)
        if started:
            conversation.set_status_started()
        conversation.add_group(group)
        yield conversation.save()
        returnValue(conversation)

    def set_conversation_tag(self, msg, conversation):
        # TOOD: Move into AppWorkerTestCase once it's working
        tag = (conversation.delivery_tag_pool, conversation.delivery_tag)
        TaggingMiddleware.add_tag_to_msg(msg, tag)
        return msg

    def mk_conv_config(self, method):
        app_js = """
            api.%(method)s = function(command) {
                this.log_info("From command: inbound-message",
                    function (reply) {
                        this.log_info("Log successful: " + reply.success);
                        this.done();
                    }
                );
            }
        """ % {'method': method}
        config = {
            'jsbox': {
                'javascript': app_js,
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
            yield self.start_conversation(conversation)
            self.assertTrue("Starting javascript sandbox conversation "
                            "(key: u'%s')." % conversation.key
                            in lc.messages())

    @inlineCallbacks
    def test_user_message(self):
        conversation = yield self.setup_conversation(
            config=self.mk_conv_config('on_inbound_message'))
        yield self.start_conversation(conversation)
        msg = self.mkmsg_in()
        yield self.dispatch_to_conv(msg, conversation)

    @inlineCallbacks
    def test_user_message_sandbox_id(self):
        conversation = yield self.setup_conversation(
            config=self.mk_conv_config('on_inbound_message'))
        yield self.start_conversation(conversation)
        msg = self.mkmsg_in()
        conversation.set_go_helper_metadata(msg['helper_metadata'])
        config = yield self.app.get_config(msg)
        self.assertEqual(config.sandbox_id, self.user_account.key)

    @inlineCallbacks
    def test_event(self):
        conversation = yield self.setup_conversation(
            config=self.mk_conv_config('on_inbound_event'))
        yield self.start_conversation(conversation)
        msg = self.mkmsg_in()
        conversation.set_go_helper_metadata(msg['helper_metadata'])
        yield self.store_outbound_msg(msg, conversation)
        event = self.mkmsg_ack(user_message_id=msg['message_id'])
        conversation.set_go_helper_metadata(event['helper_metadata'])
        yield self.dispatch_event(event)

    @inlineCallbacks
    def test_conversation_for_api(self):
        conversation = yield self.setup_conversation(started=True)
        dummy_api = self.mk_dummy_api(conversation)
        self.assertEqual(self.app.conversation_for_api(dummy_api),
                         conversation)

    @inlineCallbacks
    def test_user_api_for_api(self):
        conversation = yield self.setup_conversation(started=True)
        dummy_api = self.mk_dummy_api(conversation)
        user_api = self.app.user_api_for_api(dummy_api)
        self.assertEqual(user_api.user_account_key,
                         conversation.user_account.key)


class TestConversationConfigResource(TestCase):
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
