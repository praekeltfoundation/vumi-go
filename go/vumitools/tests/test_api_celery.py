# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_celery."""

from twisted.trial.unittest import TestCase

from go.vumitools.api import VumiApiCommand
from go.vumitools.tests.utils import CeleryTestMixIn


class TestTasks(TestCase, CeleryTestMixIn):

    def setUp(self):
        self.setup_celery_for_tests()
        from go.vumitools import api_celery
        self.api = api_celery
        self.exchange_config = VumiApiCommand.default_routing_config()

    def tearDown(self):
        self.restore_celery()

    def test_batch_send_task(self):
        consumer = self.get_consumer(**self.exchange_config)
        batch_options = {"from_addr": "test1"},
        result = self.api.batch_send_task.delay("b123", batch_options,
                                                "hello world",
                                                ["+1234", "+5678"],
                                                self.exchange_config)
        self.assertTrue(result.successful())
        self.assertEqual(result.result, None)

        [cmd1, cmd2] = self.fetch_cmds(consumer)

        self.assertEqual(cmd1,
                         VumiApiCommand.send("b123", batch_options,
                                             "hello world", "+1234"))
        self.assertEqual(cmd2,
                         VumiApiCommand.send("b123", batch_options,
                                             "hello world", "+5678"))
