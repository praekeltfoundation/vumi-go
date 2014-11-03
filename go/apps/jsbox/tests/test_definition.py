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

    def test_default_config_name_slugifying(self):
        config = ConversationDefinition.get_default_config(
            'SoMe CoNv NaMe', 'conv-description')
        app_config = json.loads(config['jsbox_app_config']['config']['value'])
        self.assertEqual(app_config['name'], 'some-conv-name')
