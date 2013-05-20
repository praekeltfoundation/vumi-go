# -*- coding: utf-8 -*-

import json

from mock import Mock
from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.log import LogManager, GoLoggingResource
from go.vumitools.tests.utils import GoPersistenceMixin


class TestTxLogManager(TestCase, GoPersistenceMixin):
    @inlineCallbacks
    def setUp(self):
        super(TestTxLogManager, self).setUp()
        yield self._persist_setUp()
        self.redis = yield self.get_redis_manager()

    @inlineCallbacks
    def tearDown(self):
        yield super(TestTxLogManager, self).tearDown()
        yield self._persist_tearDown()

    def log_manager(self, max_logs=None):
        return LogManager(self.redis, max_logs)

    @inlineCallbacks
    def test_add_log(self):
        lm = self.log_manager()
        yield lm.add_log("campaign-1", "conv-1", "Hello info!")
        logs = yield self.redis.lrange("campaign-1:conv-1", 0, -1)
        self.assertEqual(logs, ["Hello info!"])

    @inlineCallbacks
    def test_add_log_trims(self):
        lm = self.log_manager(max_logs=10)
        for i in range(10):
            yield lm.add_log("campaign-1", "conv-1", "%d" % i)
        logs = yield self.redis.lrange("campaign-1:conv-1", 0, -1)
        self.assertEqual(list(reversed(logs)), ["%d" % i for i in range(10)])

        yield lm.add_log("campaign-1", "conv-1", "10")
        logs = yield self.redis.lrange("campaign-1:conv-1", 0, -1)
        self.assertEqual(list(reversed(logs)),
                         ["%d" % i for i in range(1, 11)])

    @inlineCallbacks
    def test_get_logs(self):
        lm = self.log_manager()
        for i in range(3):
            yield self.redis.lpush("campaign-1:conv-1", str(i))
        logs = yield lm.get_logs("campaign-1", "conv-1")
        self.assertEqual(logs, ['2', '1', '0'])


class TestLogManager(TestTxLogManager):
    sync_persistence = True


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.conversation = None

    def conversation_for_api(self, api):
        return self.conversation


class TestGoLoggingResource(ResourceTestCaseBase, GoPersistenceMixin):
    app_worker_cls = StubbedAppWorker
    resource_cls = GoLoggingResource

    @inlineCallbacks
    def setUp(self):
        super(TestGoLoggingResource, self).setUp()
        yield self._persist_setUp()
        self.redis = yield self.get_redis_manager()
        yield self.create_resource({
            'redis_manager': {
                'FAKE_REDIS': self.redis,
                'key_prefix': self.redis._key_prefix,
            }
        })
        self.conversation = Mock(key="conv-1", user_account_key="campaign-1")
        self.resource.app_worker.conversation = self.conversation

    @inlineCallbacks
    def tearDown(self):
        yield super(TestGoLoggingResource, self).tearDown()
        yield self._persist_tearDown()

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
        yield self.assert_bad_command(
            'info', u'Logging expects a value for msg.')
