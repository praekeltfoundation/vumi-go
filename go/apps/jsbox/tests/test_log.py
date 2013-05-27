# -*- coding: utf-8 -*-

import json
import logging
import datetime
import re

from mock import Mock
from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import LogCatcher
from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.log import LogManager, GoLoggingResource
from go.vumitools.tests.utils import GoPersistenceMixin


class LogCheckerMixin(object):
    """Mixing for test cases that want to check logs."""
    def parse_iso_format(self, iso_string):
        dt_string, _sep, micro_string = iso_string.partition(".")
        dt = datetime.datetime.strptime(dt_string, "%Y-%m-%dT%H:%M:%S")
        microsecond = int(micro_string or '0')
        return dt.replace(microsecond=microsecond)

    def check_logs(self, actual, expected, epsilon_dt=None):
        if epsilon_dt is None:
            epsilon_dt = datetime.timedelta(seconds=5)
        zero_dt = datetime.timedelta(seconds=0)
        now = datetime.datetime.utcnow()
        log_re = re.compile(r"^\[(?P<dt>.*?), (?P<lvl>.*?)\] (?P<msg>.*)$")
        actual = list(reversed(actual))
        for msg, (expected_level, expected_msg) in zip(actual, expected):
            match = log_re.match(msg)
            self.assertTrue(match is not None,
                            "Expected formatted log message but got %r"
                            % (msg,))
            self.assertEqual(match.group('msg'), expected_msg)
            self.assertEqual(match.group('lvl'), expected_level)
            dt = self.parse_iso_format(match.group('dt'))
            self.assertTrue(zero_dt <= now - dt < epsilon_dt)
        self.assertEqual(len(actual), len(expected))


class TestTxLogManager(TestCase, GoPersistenceMixin, LogCheckerMixin):
    @inlineCallbacks
    def setUp(self):
        super(TestTxLogManager, self).setUp()
        yield self._persist_setUp()
        self.parent_redis = yield self.get_redis_manager()
        self.redis = self.parent_redis.sub_manager(
            LogManager.DEFAULT_SUB_STORE)

    @inlineCallbacks
    def tearDown(self):
        yield super(TestTxLogManager, self).tearDown()
        yield self._persist_tearDown()

    def log_manager(self, max_logs=None):
        return LogManager(self.parent_redis, max_logs)

    @inlineCallbacks
    def test_add_log(self):
        lm = self.log_manager()
        yield lm.add_log("campaign-1", "conv-1", "Hello info!", logging.INFO)
        logs = yield self.redis.lrange("campaign-1:conv-1", 0, -1)
        self.check_logs(logs, [("INFO", "Hello info!")])

    @inlineCallbacks
    def test_add_log_trims(self):
        lm = self.log_manager(max_logs=10)
        for i in range(10):
            yield lm.add_log("campaign-1", "conv-1", "%d" % i, logging.INFO)
        logs = yield self.redis.lrange("campaign-1:conv-1", 0, -1)
        self.check_logs(logs, [
            ("INFO", "%d" % i) for i in range(10)
        ])

        yield lm.add_log("campaign-1", "conv-1", "10", logging.INFO)
        logs = yield self.redis.lrange("campaign-1:conv-1", 0, -1)
        self.check_logs(logs, [
            ("INFO", "%d" % i) for i in range(1, 11)
        ])

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


class TestGoLoggingResource(ResourceTestCaseBase, GoPersistenceMixin,
                            LogCheckerMixin):
    app_worker_cls = StubbedAppWorker
    resource_cls = GoLoggingResource

    @inlineCallbacks
    def setUp(self):
        super(TestGoLoggingResource, self).setUp()
        yield self._persist_setUp()
        self.parent_redis = yield self.get_redis_manager()
        self.redis = self.parent_redis.sub_manager(
            LogManager.DEFAULT_SUB_STORE)
        yield self.create_resource({
            'redis_manager': {
                'FAKE_REDIS': self.parent_redis,
                'key_prefix': self.parent_redis.get_key_prefix(),
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
        with LogCatcher(log_level=logging.INFO) as lc:
            reply = yield self.dispatch_command('info', msg=u'Info message')
            msgs = lc.messages()
        self.assertEqual(msgs, ['Info message'])
        self.check_reply(reply)
        logs = yield self.redis.lrange("campaign-1:conv-1", 0, -1)
        self.check_logs(logs, [
            ("INFO", "Info message")
        ])

    @inlineCallbacks
    def test_handle_info_failure(self):
        yield self.assert_bad_command(
            'info', u'Value expected for msg')
