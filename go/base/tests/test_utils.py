"""Test for go.base.utils."""

from go.base.tests.utils import VumiGoDjangoTestCase
from go.errors import UnknownConversationType, UnknownRouterType
from go.base.utils import (
    get_conversation_pkg, get_conversation_definition,
    get_conversation_view_definition,
    get_router_pkg, get_router_definition,
    get_router_view_definition)


class ConversationDefinitionHelpersTestCase(VumiGoDjangoTestCase):
    def test_get_conversation_pkg(self):
        pkg = get_conversation_pkg('bulk_message', ['definition'])
        self.assertEqual(pkg.__name__, 'go.apps.bulk_message')

    def test_get_conversation_pkg_fails(self):
        self.assertRaises(UnknownConversationType,
                          get_conversation_pkg, 'unknown', ['definition'])

    def test_get_conversation_definition(self):
        conv_def = get_conversation_definition('bulk_message')
        from go.apps.bulk_message.definition import ConversationDefinition
        self.assertTrue(isinstance(conv_def, ConversationDefinition))
        self.assertEqual(conv_def.conversation_type, 'bulk_message')

    def test_get_conversation_definition_with_conv(self):
        dummy_conv = object()
        conv_def = get_conversation_definition('bulk_message', dummy_conv)
        self.assertTrue(conv_def.conv is dummy_conv)

    def test_get_conversation_view_definition(self):
        view_def = get_conversation_view_definition('bulk_message')
        from go.apps.bulk_message.view_definition import (
            ConversationViewDefinition,)
        self.assertTrue(isinstance(view_def, ConversationViewDefinition))

    def test_get_conversation_view_definition_with_conv(self):
        dummy_conv = object()
        view_def = get_conversation_view_definition('bulk_message', dummy_conv)
        self.assertTrue(view_def._conv_def.conv is dummy_conv)

    def test_get_conversation_view_definition_unknown_conv_type(self):
        self.assertRaises(
            UnknownConversationType,
            get_conversation_view_definition, 'not_droids')

    def test_get_conversation_view_definition_obsolete_conv_type(self):
        view_def = get_conversation_view_definition('wikipedia_sms')
        self.assertEqual(view_def._conv_def.conversation_type, 'wikipedia_sms')


class RouterDefinitionHelpersTestCase(VumiGoDjangoTestCase):
    def test_get_router_pkg(self):
        pkg = get_router_pkg('keyword', ['definition'])
        self.assertEqual(pkg.__name__, 'go.routers.keyword')

    def test_get_router_pkg_fails(self):
        self.assertRaises(UnknownRouterType,
                          get_router_pkg, 'unknown', ['definition'])

    def test_get_router_definition(self):
        router_def = get_router_definition('keyword')
        from go.routers.keyword.definition import RouterDefinition
        self.assertTrue(isinstance(router_def, RouterDefinition))
        self.assertEqual(router_def.router_type, 'keyword')

    def test_get_router_definition_with_router(self):
        dummy_router = object()
        router_def = get_router_definition('keyword', dummy_router)
        self.assertTrue(router_def.router is dummy_router)

    def test_get_router_view_definition(self):
        view_def = get_router_view_definition('keyword')
        from go.routers.keyword.view_definition import (
            RouterViewDefinition,)
        self.assertTrue(isinstance(view_def, RouterViewDefinition))

    def test_get_router_view_definition_with_router(self):
        dummy_router = object()
        view_def = get_router_view_definition('keyword', dummy_router)
        self.assertTrue(view_def._router_def.router is dummy_router)
