import json
from vumi.tests.helpers import VumiTestCase


from go.apps.jsbox.definition import ConversationDefinition


class TestConversationDefinition(VumiTestCase):
    def test_default_config(self):
        config = ConversationDefinition.get_default_config(
            'conv-name', 'conv-description')

        self.assertEqual(config, {
            'jsbox_app_config': {
                'config': {
                    'key': 'config',
                    'value': json.dumps({'name': 'conv-name'})
                }
            }
        })
