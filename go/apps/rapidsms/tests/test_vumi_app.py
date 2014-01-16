# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.utils import LogCatcher
from vumi.tests.helpers import VumiTestCase
from vumi.config import ConfigContext

from go.apps.tests.helpers import AppWorkerHelper
from go.apps.rapidsms.vumi_app import RapidSMSApplication, RapidSMSConfig


APP_CONFIG = {
    'web_path': '/test/',
    'web_port': 0,
}


CONV_CONFIG = {
    'rapidsms': {
        "rapidsms_url": "http://www.example.com/",
        "rapidsms_username": "rapid-user",
        "rapidsms_password": "rapid-pass",
        "rapidsms_auth_method": "basic",
        "rapidsms_http_method": "POST",
        "allowed_endpoints": [u"default", u"extra"],
    },
    'auth_tokens': {
        "api_tokens": [u"token-1"],
    },
}


class RapidSMSConfigTestCase(VumiTestCase):

    APP_CONFIG = APP_CONFIG
    CONV_CONFIG = CONV_CONFIG

    def setUp(self):
        self.app_helper = self.add_helper(AppWorkerHelper(RapidSMSApplication))

    @inlineCallbacks
    def mk_config(self, app_config, conv_config):
        app = yield self.app_helper.get_app_worker(app_config)
        config = app.config.copy()
        config.update(conv_config["rapidsms"])
        config["vumi_username"] = u"conv-1"
        config["vumi_password"] = conv_config["auth_tokens"]["api_tokens"][0]
        config["vumi_auth_method"] = "basic"
        returnValue(config)

    @inlineCallbacks
    def test_validate(self):
        config = yield self.mk_config(self.APP_CONFIG, self.CONV_CONFIG)
        RapidSMSConfig(config)


class RapidSMSApplicationTestCase(VumiTestCase):

    APP_CONFIG = APP_CONFIG
    CONV_CONFIG = CONV_CONFIG

    def setUp(self):
        self.app_helper = self.add_helper(AppWorkerHelper(RapidSMSApplication))

    def _username_for_conv(self, conv):
        return RapidSMSApplication.vumi_username_for_conversation(conv)

    @inlineCallbacks
    def test_setup_application(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        yield app.startService()

    @inlineCallbacks
    def test_teardown_application(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        yield app.startService()
        yield app.stopService()

    @inlineCallbacks
    def test_vumi_username_for_conversation(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        conv = yield self.app_helper.create_conversation(
            config=self.CONV_CONFIG)
        self.assertEqual(
            app.vumi_username_for_conversation(conv),
            "%s@%s" % (conv.user_account.key, conv.key)
        )

    @inlineCallbacks
    def test_get_config_for_message(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        conv = yield self.app_helper.create_conversation(
            config=self.CONV_CONFIG, started=True)
        msg = yield self.app_helper.make_stored_inbound(conv, "foo")
        config = yield app.get_config(msg)
        self.assertTrue(isinstance(config, RapidSMSConfig))
        self.assertEqual(config.vumi_username, self._username_for_conv(conv))

    @inlineCallbacks
    def test_get_config_for_username(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        conv = yield self.app_helper.create_conversation(
            config=self.CONV_CONFIG, started=True)
        ctxt = ConfigContext(
            username="%s@%s" % (conv.user_account.key, conv.key))
        config = yield app.get_config(None, ctxt=ctxt)
        self.assertTrue(isinstance(config, RapidSMSConfig))
        self.assertEqual(config.vumi_username, self._username_for_conv(conv))

    @inlineCallbacks
    def test_get_config_for_missing_username(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        ctxt = ConfigContext(username=None)
        d = app.get_config(None, ctxt=ctxt)
        self.assertFailure(d, ValueError)

    @inlineCallbacks
    def test_get_config_for_badly_formatted_username(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        ctxt = ConfigContext(username="foo")
        d = app.get_config(None, ctxt=ctxt)
        self.assertFailure(d, ValueError)

    @inlineCallbacks
    def test_send_rapidsms_nonreply(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        conv = yield self.app_helper.create_conversation(
            config=self.CONV_CONFIG, started=True)
        ctxt = ConfigContext(
            username="%s@%s" % (conv.user_account.key, conv.key))
        config = yield app.get_config(None, ctxt=ctxt)
        yield app.send_rapidsms_nonreply(
            "to:123", "Hello!", endpoint="default", config=config)
        [msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(msg["content"], "Hello!")
        self.assertEqual(msg["to_addr"], "to:123")
        self.assertEqual(msg.get_routing_endpoint(), "default")
        self.assertEqual(msg["helper_metadata"], {
            u'go': {
                u'conversation_type': "rapidsms",
                u'user_account': conv.user_account.key,
                u'conversation_key': conv.key,
            }
        })

    @inlineCallbacks
    def test_process_command_start(self):
        yield self.app_helper.get_app_worker(self.APP_CONFIG)
        conv = yield self.app_helper.create_conversation(
            config=self.CONV_CONFIG)
        with LogCatcher() as lc:
            yield self.app_helper.start_conversation(conv)
            self.assertTrue("Starting RapidSMS conversation "
                            "(key: u'%s')." % conv.key
                            in lc.messages())
