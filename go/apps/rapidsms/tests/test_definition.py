from vumi.tests.helpers import VumiTestCase

from go.apps.rapidsms.definition import ConversationDefinition


class TestConversationDefinition(VumiTestCase):
    def test_conversation_type(self):
        conv_def = ConversationDefinition()
        self.assertEqual(conv_def.conversation_type, "rapidsms")
