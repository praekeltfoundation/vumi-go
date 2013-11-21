"""Tests for go.config."""

from twisted.trial.unittest import TestCase

from go.config import (
    get_conversation_pkg, get_router_pkg,
    get_conversation_definition, get_router_definition,
    configured_conversation_types, configured_router_types,
    configured_conversations, configured_routers,
    obsolete_conversation_types, obsolete_router_types)
from go.errors import UnknownConversationType, UnknownRouterType


class ConversationDefinitionHelpersTestCase(TestCase):
    def test_configured_conversation_types(self):
        conv_types = configured_conversation_types()
        self.assertEqual(conv_types['bulk_message'], 'Group Message')

    def test_configured_conversations(self):
        convs = configured_conversations()
        self.assertEqual(convs['go.apps.bulk_message'], {
            'namespace': 'bulk_message',
            'display_name': 'Group Message',
        })

    def test_obsolete_conversation_types(self):
        obsolete_types = obsolete_conversation_types()
        self.assertEqual(obsolete_types, set([
            'wikipedia_sms', 'wikipedia_ussd',
        ]))

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


class RouterDefinitionHelpersTestCase(TestCase):
    def test_configured_router_types(self):
        conv_types = configured_router_types()
        self.assertEqual(conv_types['keyword'], 'Keyword')

    def test_configured_routers(self):
        routers = configured_routers()
        self.assertEqual(routers['go.routers.keyword'], {
            'namespace': 'keyword',
            'display_name': 'Keyword',
        })

    def test_obsolete_router_types(self):
        obsolete_types = obsolete_router_types()
        self.assertEqual(obsolete_types, set([
        ]))

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
