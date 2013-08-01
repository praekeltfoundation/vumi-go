"""Tests for go.api.go_api.action_dispatcher."""

from mock import Mock

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from vumi.tests.utils import LogCatcher

from go.api.go_api.action_dispatcher import (
    ActionDispatcher, ActionError, ConversationActionDispatcher,
    RouterActionDispatcher)


class SimpleActionDispatcher(ActionDispatcher):

    def handle_do_thing(self, obj, foo):
        self.user_api.do_thing(obj, foo)
        return {"success": True}


class ActionDispatcherTestCase(TestCase):

    def test_dispatcher_type_name(self):
        self.assertEqual(ActionDispatcher.dispatcher_type_name, None)

    def test_unknown_action(self):
        dispatcher = ActionDispatcher(Mock())
        obj = Mock(key="abc")
        self.assertRaises(ActionError, dispatcher.unknown_action,
                          obj, foo="bar")

    @inlineCallbacks
    def test_dispatch_action(self):
        user_api = Mock(do_thing=Mock())
        dispatcher = SimpleActionDispatcher(user_api)
        obj = Mock(key="abc")
        with LogCatcher() as lc:
            result = yield dispatcher.dispatch_action(
                obj, "do_thing", {"foo": "bar"})
            [msg] = lc.messages()
            self.assertEqual(msg, "Performed action 'do_thing' on None 'abc'.")
        self.assertEqual(result, {"success": True})
        self.assertTrue(user_api.do_thing.called_once_with(obj, "bar"))

    @inlineCallbacks
    def test_dispatch_action_which_errors(self):
        dispatcher = ActionDispatcher(Mock())
        obj = Mock(key="abc")
        with LogCatcher() as lc:
            try:
                yield dispatcher.dispatch_action(
                    obj, "weird_action", {"foo": "bar"})
            except ActionError, e:
                self.assertEqual(e.faultString, "Unknown action.")
            else:
                self.fail("Expected ActionError.")
            [err] = lc.errors
            self.assertEqual(err["why"],
                             "Action 'weird_action' on None %r (key: 'abc')"
                             " with params {'foo': 'bar'} failed." % obj)
        [err] = self.flushLoggedErrors(ActionError)
        self.assertEqual(err.value.faultString, "Unknown action.")


class ConversationAcitonDispatcherTestCase(TestCase):
    def test_dispatcher_type_name(self):
        self.assertEqual(
            ConversationActionDispatcher.dispatcher_type_name, 'conversation')


class RouterActionDispatcherTestCase(TestCase):
    def test_dispatcher_type_name(self):
        self.assertEqual(RouterActionDispatcher.dispatcher_type_name, 'router')
