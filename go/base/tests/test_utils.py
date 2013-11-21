"""Test for go.base.utils."""

from go.base.tests.helpers import GoDjangoTestCase
import go.base.utils
from go.base.utils import (
    get_conversation_view_definition, get_router_view_definition)
from go.errors import UnknownConversationType, UnknownRouterType
from go.vumitools.tests.helpers import PatchHelper


class TestConversationDefinitionHelpers(GoDjangoTestCase):
    def setUp(self):
        self.patch_helper = PatchHelper()
        self.add_cleanup(self.patch_helper.cleanup)

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
        self.patch_helper.monkey_patch(
            go.base.utils, 'obsolete_conversation_types',
            lambda: set(['old_conv']))
        view_def = get_conversation_view_definition('old_conv')
        self.assertEqual(view_def._conv_def.conversation_type, 'old_conv')


class TestRouterDefinitionHelpers(GoDjangoTestCase):
    def setUp(self):
        self.patch_helper = PatchHelper()
        self.add_cleanup(self.patch_helper.cleanup)

    def test_get_router_view_definition(self):
        view_def = get_router_view_definition('keyword')
        from go.routers.keyword.view_definition import (
            RouterViewDefinition,)
        self.assertTrue(isinstance(view_def, RouterViewDefinition))

    def test_get_router_view_definition_with_router(self):
        dummy_router = object()
        view_def = get_router_view_definition('keyword', dummy_router)
        self.assertTrue(view_def._router_def.router is dummy_router)

    def test_get_router_view_definition_unknown_conv_type(self):
        self.assertRaises(
            UnknownRouterType,
            get_router_view_definition, 'not_the_router_we_are_looking_for')

    def test_get_router_view_definition_obsolete_router_type(self):
        self.patch_helper.monkey_patch(
            go.base.utils, 'obsolete_router_types',
            lambda: set(['old_router']))
        view_def = get_router_view_definition('old_router')
        self.assertEqual(view_def._router_def.router_type, 'old_router')
