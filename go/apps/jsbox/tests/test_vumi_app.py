# -*- coding: utf-8 -*-
from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.utils import ApplicationTestCase

from go.apps.jsbox.vumi_app import JsBoxApplication


class JsBoxApplication(ApplicationTestCase):

    use_riak = True
    application_class = JsBoxApplication

    @inlineCallbacks
    def setUp(self):
        yield super(JsBoxApplication, self).setUp()
        self.config = self.mk_config({
            'metrics_prefix': 'jsbox_metrics',
            })
        self.app = yield self.get_application(self.config)

    def test_something(self):
        self.assertEqual(1, 1)
