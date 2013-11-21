"""Tests for go.api.go_api.action_dispatcher."""

from mock import Mock

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.api.go_api.action_dispatcher import (
    ActionDispatcher, ActionError, ConversationActionDispatcher,
    RouterActionDispatcher)


class SimpleActionDispatcher(ActionDispatcher):

    dispatcher_type_name = "simple_object"

    def action_do_thing(self, user_api, obj, foo):
        user_api.do_thing(obj, foo)
        return {"success": True}

    def get_object_by_key(self, user_api, obj_key):
        return user_api.get_object(obj_key)


class TestActionDispatcher(VumiTestCase):

    def test_dispatcher_type_name(self):
        self.assertEqual(ActionDispatcher.dispatcher_type_name, None)

    def mk_dispatcher(self, user_account_key=u"abc", object_key=u"xyz"):
        obj = Mock(key=object_key)
        user_api = Mock(do_thing=Mock(), get_object=Mock(return_value=obj))
        vumi_api = Mock(get_user_api=Mock(return_value=user_api))
        dispatcher = SimpleActionDispatcher(user_account_key, vumi_api)
        return obj, user_api, dispatcher

    @inlineCallbacks
    def test_jsonrpc_handler(self):
        user_account_key = u"abc"
        obj, user_api, dispatcher = self.mk_dispatcher(user_account_key)
        result = yield dispatcher.jsonrpc_do_thing(
            user_account_key, obj.key, {"foo": "bar"})
        self.assertEqual(result, {"success": True})

    @inlineCallbacks
    def test_dispatch_action(self):
        user_account_key = u"abc"
        obj, user_api, dispatcher = self.mk_dispatcher(user_account_key)
        handler = dispatcher.__class__.action_do_thing
        result = yield dispatcher.dispatch_action(
            handler, u"abc", obj.key, {"foo": "bar"})
        self.assertEqual(result, {"success": True})
        self.assertTrue(user_api.do_thing.called_once_with(obj, "bar"))
        self.assertTrue(
            dispatcher.vumi_api.get_user_api.called_once_with(
                user_account_key))


class TestActionError(VumiTestCase):
    def test_action_error(self):
        err = ActionError("Testing")
        self.assertEqual(err.faultString, "Testing")
        self.assertEqual(err.faultCode, 400)


class TestConversationAcitonDispatcher(VumiTestCase):
    def test_dispatcher_type_name(self):
        self.assertEqual(
            ConversationActionDispatcher.dispatcher_type_name, 'conversation')


class TestRouterActionDispatcher(VumiTestCase):
    def test_dispatcher_type_name(self):
        self.assertEqual(RouterActionDispatcher.dispatcher_type_name, 'router')
