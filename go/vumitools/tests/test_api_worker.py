# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase

from go.vumitools.api_worker import VumiApiWorker
from go.vumitools.api import VumiApiCommand


class TestVumiApiWorker(ApplicationTestCase):

    application_class = VumiApiWorker

    @inlineCallbacks
    def setUp(self):
        super(TestVumiApiWorker, self).setUp()
        self.api = yield self.get_application({})

    def publish_command(self, cmd):
        return self.dispatch(cmd, rkey='vumi.api')

    @inlineCallbacks
    def test_send(self):
        yield self.publish_command(VumiApiCommand.send('batch1', 'content',
                                                       'to_addr'))
        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg['to_addr'], 'to_addr')
        self.assertEqual(msg['content'], 'content')
