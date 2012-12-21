"""Tests for go.apps.jsbox.outbound."""

import mock

from twisted.trial.unittest import TestCase

from vumi.application.sandbox import SandboxCommand
from vumi.tests.utils import LogCatcher

from go.apps.jsbox.outbound import GoOutboundResource


class TestGoOutboundResource(TestCase):

    def setUp(self):
        self.conversation = mock.Mock()
        self.app_worker = mock.Mock()
        self.dummy_api = object()
        self.resource = GoOutboundResource("test", self.app_worker, {})
        self.app_worker.conversation_for_api = mock.Mock(
            return_value=self.conversation)

    def check_reply(self, reply, cmd, success):
        self.assertEqual(reply['reply'], True)
        self.assertEqual(reply['cmd_id'], cmd['cmd_id'])
        self.assertEqual(reply['success'], success)
