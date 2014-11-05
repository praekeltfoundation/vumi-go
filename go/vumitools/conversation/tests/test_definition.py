from vumi.tests.helpers import VumiTestCase

from go.vumitools.tests.helpers import VumiApiHelper
from go.vumitools.conversation.definition import ConversationDefinitionBase


class DummyConversationDefinition(ConversationDefinitionBase):
    def configured_endpoints(self, config):
        return config['endpoints']


class TestConversationDefinitionBase(VumiTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(VumiApiHelper(is_sync=True))
        self.user_helper = self.vumi_helper.get_or_create_user()
        self.conv = self.user_helper.create_conversation(u'jsbox')

    def test_get_endpoints(self):
        dfn = DummyConversationDefinition(self.conv)
        self.assertEqual(
            dfn.get_endpoints({'endpoints': ['foo', 'bar']}),
            ['foo', 'bar'])

    def test_get_endpoints_extra_endpoints(self):
        class ConversationDefinition(DummyConversationDefinition):
            extra_static_endpoints = ('foo', 'bar')

        dfn = ConversationDefinition(self.conv)
        self.assertEqual(
            dfn.get_endpoints({'endpoints': ['baz', 'quux']}),
            ['foo', 'bar', 'baz', 'quux'])
