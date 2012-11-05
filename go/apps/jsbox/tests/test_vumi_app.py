# -*- coding: utf-8 -*-
from twisted.internet.defer import inlineCallbacks

from go.vumitools.tests.utils import AppWorkerTestCase

from go.apps.jsbox.vumi_app import JsBoxApplication


class JsBoxApplication(AppWorkerTestCase):

    use_riak = True
    application_class = JsBoxApplication

    @inlineCallbacks
    def setUp(self):
        yield super(JsBoxApplication, self).setUp()
        self.config = self.mk_config({
            'metrics_prefix': 'jsbox_metrics',
            })
        self.app = yield self.get_application(self.config)

    @inlineCallbacks
    def test_start(self):
        yield self.dispatch_command("start", command_data={
                    "batch_id": "batch-id",
                    "conversation_type": "jsbox",
                    "conversation_key": "key",
                    "is_client_initiated": False,
                    "msg_options": {}
                    })
