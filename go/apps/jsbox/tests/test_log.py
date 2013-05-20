# -*- coding: utf-8 -*-

import json

from mock import Mock
from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.log import LogManager, GoLoggingResource


class TestLogManager(TestCase):
    def setUp(self):
        pass

    def log_manager(self, max_logs=None):
        return LogManager(self.redis, max_logs)

    def test_add_log(self):
        pass

    def test_add_log_trims(self):
        pass

    def test_get_logs(self):
        pass


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.conversation = None

    def conversation_for_api(self, api):
        return self.conversation


class TestGoLoggingResource(ResourceTestCaseBase):
    app_worker_cls = StubbedAppWorker
    resource_cls = GoLoggingResource

    @inlineCallbacks
    def setUp(self):
        super(TestGoLoggingResource, self).setUp()
        yield self.create_resource({})

    def check_reply(self, reply, **kw):
        kw.setdefault('success', True)

        # get a dict of the reply fields that we can pop items off without
        # worrying about modifying the actual reply
        reply = json.loads(reply.to_json())

        for field_name, expected_value in kw.iteritems():
            self.assertEqual(reply[field_name], expected_value)

    @inlineCallbacks
    def assert_bad_command(self, cmd, reason, **kw):
        reply = yield self.dispatch_command(cmd, **kw)
        self.check_reply(reply, success=False, reason=reason)

    @inlineCallbacks
    def test_handle_info(self):
        reply = yield self.dispatch_command('info', msg=u'Info message')
        self.check_reply(reply)

    @inlineCallbacks
    def test_handle_info_failure(self):
        self.assert_bad_command('info', 'Logging expects a value for msg')
