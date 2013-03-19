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

    def test_send_command_task(self):
        consumer = self.get_consumer(**self.exchange_config)
        cmd = VumiApiCommand(worker_name='worker_1', command='foo')
        result = self.api.send_command_task.delay(cmd, self.exchange_config)
        self.assertTrue(result.successful())
        self.assertEqual(result.result, None)

        [cmd1] = self.fetch_cmds(consumer)

        self.assertEqual(cmd1, cmd)
