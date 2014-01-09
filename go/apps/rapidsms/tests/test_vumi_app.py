# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.utils import LogCatcher
from vumi.tests.helpers import VumiTestCase

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

    @inlineCallbacks
    def test_setup_application(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        yield app.startService()
        # TODO: check something?

    @inlineCallbacks
    def test_teardown_application(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        yield app.startService()
        yield app.stopService()
        # TODO: check something?

    @inlineCallbacks
    def test_get_config(self):
        app = yield self.app_helper.get_app_worker(self.APP_CONFIG)
        conv = yield self.app_helper.create_conversation(
            config=self.CONV_CONFIG, started=True)
        msg = yield self.app_helper.make_stored_inbound(conv, "foo")
        config = yield app.get_config(msg)
        self.assertTrue(isinstance(config, RapidSMSConfig))

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
