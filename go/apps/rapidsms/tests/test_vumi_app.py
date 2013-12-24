# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import LogCatcher
from vumi.tests.helpers import VumiTestCase

from go.apps.tests.helpers import AppWorkerHelper
from go.apps.rapidsms.vumi_app import RapidSMSApplication, RapidSMSConfig


class RapidSMSConfigTestCase(VumiTestCase):
    # TODO: implement
    pass


class RapidSMSApplicationTestCase(VumiTestCase):

    APP_CONFIG = {
        'web_path': '/test/',
        'web_port': 0,
    }

    CONV_CONFIG = {
    }

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
        conv = yield self.app_helper.create_conversation(self.CONV_CONFIG)
        with LogCatcher() as lc:
            yield self.app_helper.start_conversation(conv)
            self.assertTrue("Starting RapidSMS conversation "
                            "(key: u'%s')." % conv.key
                            in lc.messages())
