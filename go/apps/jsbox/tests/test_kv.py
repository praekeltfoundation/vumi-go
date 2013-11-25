# -*- coding: utf-8 -*-

import json
import logging
import datetime
import re

from mock import Mock
from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import LogCatcher

from go.apps.jsbox.kv import KeyValueManager
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


class TestTxKeyValueManager(TestCase, GoPersistenceMixin, LogCheckerMixin):
    @inlineCallbacks
    def setUp(self):
        super(TestTxKeyValueManager, self).setUp()
        yield self._persist_setUp()
        self.parent_redis = yield self.get_redis_manager()
        self.redis = self.parent_redis.sub_manager(
            KeyValueManager.DEFAULT_SUB_STORE)

    @inlineCallbacks
    def tearDown(self):
        yield super(TestTxKeyValueManager, self).tearDown()
        yield self._persist_tearDown()

    def kv_manager(self):
        return KeyValueManager(self.parent_redis)

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


class TestKeyValueManager(TestTxKeyValueManager):
    sync_persistence = True
