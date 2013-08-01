"""Tests for go.api.go_api.action_dispatcher."""

from twisted.trial.unittest import TestCase

from go.api.go_api.action_dispatcher import (
    ActionDispatcher, ActionError, ConversationActionDispatcher,
    RouterActionDispatcher)


class ActionDispatcherTestCase(TestCase):
    def test_dispatcher_type_name(self):
        self.assertEqual(ActionDispatcher.dispatcher_type_name, None)


class ConversationAcitonDispatcherTestCase(TestCase):
    def test_dispatcher_type_name(self):
        self.assertEqual(
            ConversationActionDispatcher.dispatcher_type_name, 'conversation')


class RouterActionDispatcherTestCase(TestCase):
    def test_dispatcher_type_name(self):
        self.assertEqual(RouterActionDispatcher.dispatcher_type_name, 'router')
