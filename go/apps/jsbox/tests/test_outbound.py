"""Tests for go.apps.jsbox.outbound."""

from mock import Mock

from twisted.internet.defer import inlineCallbacks, succeed

from vumi.tests.utils import LogCatcher
from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.outbound import GoOutboundResource
from go.vumitools.tests.helpers import GoMessageHelper


class StubbedAppWorker(DummyAppWorker):

    class DummyApi(DummyAppWorker.DummyApi):
        def __init__(self, inbound_messages):
            self._inbound_messages = inbound_messages

        def get_inbound_message(self, msg_id):
            return self._inbound_messages.get(msg_id)

    sandbox_api_cls = DummyApi

    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.conversation = Mock(
            extra_endpoints=set([
                "pool1:1234", "pool2:1234", "extra_endpoint"]))
        self.send_to = Mock(return_value=succeed(None))
        self.reply_to = Mock(return_value=succeed(None))
        self.reply_to_group = Mock(return_value=succeed(None))

        self._inbound_messages = {}

    def create_sandbox_api(self):
        return self.sandbox_api_cls(self._inbound_messages)

    def user_api_for_api(self, api):
        return self.user_api

    def conversation_for_api(self, api):
        return self.conversation

    def add_inbound_message(self, msg):
        self._inbound_messages[msg['message_id']] = msg


class TestGoOutboundResource(ResourceTestCaseBase):
    app_worker_cls = StubbedAppWorker
    resource_cls = GoOutboundResource

    @inlineCallbacks
    def setUp(self):
        super(TestGoOutboundResource, self).setUp()
        yield self.create_resource({})
        self.msg_helper = self.add_helper(GoMessageHelper())

    def check_reply(self, reply, **kw):
        kw.setdefault('success', True)
        for key, expected_value in kw.iteritems():
            self.assertEqual(reply[key], expected_value)

    @inlineCallbacks
    def assert_cmd_fails(self, reason, cmd, **cmd_args):
        reply = yield self.dispatch_command(cmd, **cmd_args)
        self.check_reply(reply, success=False, reason=reason)
        self.assertFalse(self.app_worker.send_to.called)
        self.assertFalse(self.app_worker.reply_to.called)
        self.assertFalse(self.app_worker.reply_to_group.called)

    def make_inbound(self, content, **kw):
        msg = self.msg_helper.make_inbound(content, **kw)
        self.app_worker.add_inbound_message(msg)
        return msg

    def dummy_metadata_adder(self, md=None):
        if md is None:
            md = {}
        md['new'] = 'foo'
        return md

    @inlineCallbacks
    def test_reply_to(self):
        msg = self.make_inbound('Hello', helper_metadata={'orig': 'data'})
        msg_reply = msg.reply('Reply!')
        self.app_worker.conversation.set_go_helper_metadata = (
            self.dummy_metadata_adder)

        reply = yield self.dispatch_command(
            'reply_to', content=msg_reply['content'],
            in_reply_to=msg['message_id'])

        self.check_reply(reply)
        self.app_worker.reply_to.assert_called_once_with(
            msg, 'Reply!', continue_session=True,
            helper_metadata={'orig': 'data', 'new': 'foo'})

    @inlineCallbacks
    def test_reply_to_with_null_content(self):
        msg = self.make_inbound('Hello')
        msg_reply = msg.reply(None, continue_session=False)
        self.app_worker.conversation.set_go_helper_metadata = (
            lambda md: md)

        reply = yield self.dispatch_command(
            'reply_to', content=msg_reply['content'],
            continue_session=False, in_reply_to=msg['message_id'])

        self.check_reply(reply)
        self.app_worker.reply_to.assert_called_once_with(
            msg, None, continue_session=False, helper_metadata={})

    def test_reply_to_fails_with_no_content(self):
        return self.assert_cmd_fails(
            "'content' must be given in replies.",
            'reply_to', in_reply_to=u'unknown')

    def test_reply_to_fails_with_bad_content(self):
        return self.assert_cmd_fails(
            "'content' must be unicode or null.",
            'reply_to', content=5, in_reply_to=u'unknown')

    def test_reply_to_fails_with_no_in_reply_to(self):
        return self.assert_cmd_fails(
            "'in_reply_to' must be given in replies.",
            'reply_to', content=u'foo')

    def test_reply_to_fails_with_bad_id(self):
        return self.assert_cmd_fails(
            "Could not find original message with id: u'unknown'",
            'reply_to', content='Hello?', in_reply_to=u'unknown')

    @inlineCallbacks
    def test_reply_to_group(self):
        msg = self.make_inbound('Hello', helper_metadata={'orig': 'data'})
        msg_reply = msg.reply('Reply!')
        self.app_worker.conversation.set_go_helper_metadata = (
            self.dummy_metadata_adder)

        reply = yield self.dispatch_command(
            'reply_to_group', content=msg_reply['content'],
            in_reply_to=msg['message_id'])

        self.check_reply(reply)
        self.app_worker.reply_to_group.assert_called_once_with(
            msg, 'Reply!', continue_session=True,
            helper_metadata={'orig': 'data', 'new': 'foo'})

    def test_reply_to_group_fails_with_no_content(self):
        return self.assert_cmd_fails(
            "'content' must be given in replies.",
            'reply_to_group', in_reply_to=u'unknown')

    def test_reply_to_group_fails_with_no_in_reply_to(self):
        return self.assert_cmd_fails(
            "'in_reply_to' must be given in replies.",
            'reply_to_group', content=u'foo')

    def test_reply_to_group_fails_with_bad_id(self):
        return self.assert_cmd_fails(
            "Could not find original message with id: u'unknown'",
            'reply_to_group', content='Hello?', in_reply_to=u'unknown')

    def assert_sent(self, to_addr, content, msg_options):
        self.app_worker.send_to.assert_called_once_with(
            to_addr, content, **msg_options)

    def assert_send_to_tag_fails(self, reason, **cmd_args):
        return self.assert_cmd_fails(reason, 'send_to_tag', **cmd_args)

    def assert_send_to_endpoint_fails(self, reason, **cmd_args):
        return self.assert_cmd_fails(reason, 'send_to_endpoint', **cmd_args)

    @inlineCallbacks
    def test_send_to_tag(self):
        with LogCatcher() as lc:
            reply = yield self.dispatch_command(
                'send_to_tag', tagpool='pool1', tag='1234', to_addr='6789',
                content='bar')
            self.assertEqual(lc.messages(), [
                "Sending outbound message to u'6789' via tag "
                "(u'pool1', u'1234'), content: u'bar'"])
        self.check_reply(reply)
        self.assert_sent('6789', 'bar', {'endpoint': 'pool1:1234'})

    def test_send_to_tag_unacquired(self):
        return self.assert_send_to_tag_fails(
            "Tag (u'foo', u'12345') not held by account",
            tagpool='foo', tag='12345', to_addr='6789',
            content='bar')

    def test_send_to_tag_missing_tagpool(self):
        return self.assert_send_to_tag_fails(
            "Tag, content or to_addr not specified",
            tag='12345', to_addr='6789', content='bar')

    def test_send_to_tag_missing_tag(self):
        return self.assert_send_to_tag_fails(
            "Tag, content or to_addr not specified",
            tagpool='foo', to_addr='6789', content='bar')

    def test_send_to_tag_missing_to_addr(self):
        return self.assert_send_to_tag_fails(
            "Tag, content or to_addr not specified",
            tagpool='foo', tag='12345', content='bar')

    def test_send_to_tag_missing_content(self):
        return self.assert_send_to_tag_fails(
            "Tag, content or to_addr not specified",
            tagpool='foo', tag='12345', to_addr='6789')

    @inlineCallbacks
    def test_send_to_endpoint(self):
        with LogCatcher() as lc:
            reply = yield self.dispatch_command(
                'send_to_endpoint', endpoint='extra_endpoint', to_addr='6789',
                content='bar')
            self.assertEqual(lc.messages(), [
                "Sending outbound message to u'6789' via endpoint "
                "u'extra_endpoint', content: u'bar'"])
        self.check_reply(reply)
        self.assert_sent('6789', 'bar', {'endpoint': 'extra_endpoint'})

    @inlineCallbacks
    def test_send_to_endpoint_null_content(self):
        with LogCatcher() as lc:
            reply = yield self.dispatch_command(
                'send_to_endpoint', endpoint='extra_endpoint', to_addr='6789',
                content=None)
            self.assertEqual(lc.messages(), [
                "Sending outbound message to u'6789' via endpoint "
                "u'extra_endpoint', content: None"])
        self.check_reply(reply)
        self.assert_sent('6789', None, {'endpoint': 'extra_endpoint'})

    def test_send_to_endpoint_not_configured(self):
        return self.assert_send_to_endpoint_fails(
            "Endpoint u'bad_endpoint' not configured",
            endpoint='bad_endpoint', to_addr='6789',
            content='bar')

    def test_send_to_endpoint_missing_content(self):
        return self.assert_send_to_endpoint_fails(
            "'content' must be given in sends.",
            endpoint='extra_endpoint', to_addr='6789')

    def test_send_to_endpoint_bad_content(self):
        return self.assert_send_to_endpoint_fails(
            "'content' must be unicode or null.",
            content=3, endpoint='extra_endpoint', to_addr='6789')

    def test_send_to_endpoint_missing_endpoint(self):
        return self.assert_send_to_endpoint_fails(
            "'endpoint' must be given in sends.",
            to_addr='6789', content='bar')

    def test_send_to_endpoint_bad_endpoint(self):
        return self.assert_send_to_endpoint_fails(
            "'endpoint' must be given in sends.",
            endpoint=None, to_addr='6789', content='bar')

    def test_send_to_endpoint_missing_to_addr(self):
        return self.assert_send_to_endpoint_fails(
            "'to_addr' must be given in sends.",
            endpoint='extra_endpoint', content='bar')

    def test_send_to_endpoint_bad_to_addr(self):
        return self.assert_send_to_endpoint_fails(
            "'to_addr' must be given in sends.",
            to_addr=None, endpoint='extra_endpoint', content='bar')
