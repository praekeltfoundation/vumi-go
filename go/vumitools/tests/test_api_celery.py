# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_celery."""

import os

from twisted.trial.unittest import TestCase
from celery.app import app_or_default

from go.vumitools.api import VumiApiCommand


class TestTasks(TestCase):

    def setUp(self):
        self._setup_celery_for_tests()
        from go.vumitools import api_celery
        self.api = api_celery
        self.exchange_config = {}

    def tearDown(self):
        self._restore_celery()

    def _setup_celery_for_tests(self):
        self._celery_config = os.environ.get("CELERY_CONFIG_MODULE")
        os.environ["CELERY_CONFIG_MODULE"] = "celery.tests.config"
        self._app = app_or_default()
        self._prev = self._app.conf.CELERY_ALWAYS_EAGER
        self._app.conf.CELERY_ALWAYS_EAGER = True

    def _restore_celery(self):
        if self._celery_config is None:
            del os.environ["CELERY_CONFIG_MODULE"]
        else:
            os.environ["CELERY_CONFIG_MODULE"] = self._celery_config
        self._app.conf.CELERY_ALWAYS_EAGER = self._prev

    def _fetch(self, consumer):
        msgs = []
        while True:
            msg = consumer.fetch()
            if msg is not None:
                msgs.append(msg.payload)
            else:
                break
        return msgs

    def test_batch_send_task(self):
        consumer = self.api.batch_send_task.get_consumer(
            self.exchange_config)
        result = self.api.batch_send_task.delay("b123", "hello world",
                                                ["+1234", "+5678"],
                                                self.exchange_config)
        self.assertTrue(result.successful())
        self.assertEqual(result.result, None)

        [cmd1, cmd2] = [VumiApiCommand(**payload) for payload
                        in self._fetch(consumer)]

        self.assertEqual(cmd1,
                         VumiApiCommand.send("b123", "hello world", "+1234"))
        self.assertEqual(cmd2,
                         VumiApiCommand.send("b123", "hello world", "+5678"))
