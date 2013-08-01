"""Tests for go.api.go_api.action_dispatcher."""

from mock import Mock

from twisted.trial.unittest import TestCase

from vumi.tests.utils import LogCatcher

from go.api.go_api.action_dispatcher import (
    ActionDispatcher, ActionError, ConversationActionDispatcher,
    RouterActionDispatcher)


class ActionDispatcherTestCase(TestCase):

    def test_dispatcher_type_name(self):
        self.assertEqual(ActionDispatcher.dispatcher_type_name, None)

    def test_unknown_action(self):
        dispatcher = ActionDispatcher(Mock())
        obj = Mock(key="abc")
        self.assertRaises(ActionError, dispatcher.unknown_action,
                          obj, foo="bar")

    def test_dispatch_action_which_errors(self):
        dispatcher = ActionDispatcher(Mock())
        obj = Mock(key="abc")
        with LogCatcher() as lc:
            self.assertRaises(ActionError, dispatcher.dispatch_action,
                              obj, "weird_action", {"foo": "bar"})
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
