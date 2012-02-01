# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_celery."""

from twisted.trial.unittest import TestCase

from go.vumitools.api import VumiApiCommand
from go.vumitools.tests.utils import setup_celery_for_tests, restore_celery


class TestTasks(TestCase):

    def setUp(self):
        self._celery_setup = setup_celery_for_tests()
        from go.vumitools import api_celery
        self.api = api_celery
        self.exchange_config = {}

    def tearDown(self):
        restore_celery(*self._celery_setup)

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
