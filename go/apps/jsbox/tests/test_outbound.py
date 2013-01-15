"""Tests for go.apps.jsbox.outbound."""

import mock

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from vumi.application.sandbox import SandboxCommand
from vumi.tests.utils import LogCatcher

from go.apps.jsbox.outbound import GoOutboundResource


class TestGoOutboundResource(TestCase):

    def setUp(self):
        self.conversation = mock.Mock()
        self.user_api = mock.Mock()
        self.app_worker = mock.Mock()
        self.dummy_api = object()
        self.resource = GoOutboundResource("test", self.app_worker, {})
        self.app_worker.conversation_for_api = mock.Mock(
            return_value=self.conversation)
        self.app_worker.user_api_for_api = mock.Mock(
            return_value=self.user_api)
        self.user_api.list_endpoints = mock.Mock(
            return_value=set([('pool1', '1234'), ('pool2', '1234')]))
        self.user_api.msg_options = mock.Mock(
            return_value={'opt1': 'bar'})

    def assert_reply(self, reply, cmd, success):
        self.assertEqual(reply['reply'], True)
        self.assertEqual(reply['cmd_id'], cmd['cmd_id'])
        self.assertEqual(reply['success'], success)

    def assert_sent(self, to_addr, content, **msg_options):
        self.app_worker.send_to.assert_called_once_with(
            to_addr, content, **msg_options)

    def assert_not_sent(self):
        self.assertFalse(self.app_worker.send_to.called)

    @inlineCallbacks
    def assert_fails(self, reason, handler=None, **cmd_args):
        if handler is None:
            handler = self.resource.handle_send_to_tag
        cmd = SandboxCommand(**cmd_args)
        reply = yield handler(self.dummy_api, cmd)
        self.assert_reply(reply, cmd, False)
        self.assert_not_sent()
        self.assertEqual(reply['reason'], reason)

    def test_send_to_fails(self):
        return self.assert_fails("Generic sending not supported in Vumi Go",
                                 handler=self.resource.handle_send_to)

    @inlineCallbacks
    def test_send_to_tag(self):
        cmd = SandboxCommand(tagpool='pool1', tag='1234', to_addr='6789',
                             content='bar')
        with LogCatcher() as lc:
            reply = yield self.resource.handle_send_to_tag(self.dummy_api, cmd)
            self.assertEqual(lc.messages(), [
                "Sending outbound message to '6789' via tag ('pool1', '1234'),"
                " content: 'bar'"])
        self.assert_reply(reply, cmd, True)
        self.assert_sent('6789', 'bar', **{'opt1': 'bar'})

    def test_send_to_tag_unacquired(self):
        return self.assert_fails("Tag ('foo', '12345') not held by account",
                                 tagpool='foo', tag='12345', to_addr='6789',
                                 content='bar')

    def test_send_to_tag_missing_tagpool(self):
        return self.assert_fails("Tag, content or to_addr not specified",
                                 tag='12345', to_addr='6789', content='bar')

    def test_send_to_tag_missing_tag(self):
        return self.assert_fails("Tag, content or to_addr not specified",
                                 tagpool='foo', to_addr='6789', content='bar')

    def test_send_to_tag_missing_to_addr(self):
        return self.assert_fails("Tag, content or to_addr not specified",
                                 tagpool='foo', tag='12345', content='bar')

    def test_send_to_tag_missing_content(self):
        return self.assert_fails("Tag, content or to_addr not specified",
                                 tagpool='foo', tag='12345', to_addr='6789')
