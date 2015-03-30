from vumi.tests.helpers import VumiTestCase


from go.vumitools.tests.helpers import VumiApiHelper
from go.apps.dialogue.definition import ConversationDefinition
from go.apps.dialogue.tests.dummy_polls import simple_poll


class TestConversationDefinition(VumiTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(VumiApiHelper(is_sync=True))
        self.user_helper = self.vumi_helper.get_or_create_user()
        self.user_api = self.user_helper.user_api
        self.conv = self.user_helper.create_conversation(u'jsbox')

    def test_configured_endpoints(self):
        poll = simple_poll()

        poll['channel_types'] = [{
            'name': 'sms',
            'label': 'SMS'
        }, {
            'name': 'twitter',
            'label': 'Twitter'
        }]

        poll['states'] = [{
            'type': 'foo'
        }, {
            'type': 'send',
            'channel_type': 'sms'
        }, {
            'type': 'foo'
        }, {
            'type': 'send',
            'channel_type': 'twitter'
        }, {
            'type': 'send',
            'channel_type': 'sms'
        }]

        dfn = ConversationDefinition(self.conv)

        self.assertEqual(
            dfn.configured_endpoints({'poll': poll}),
            ['SMS', 'Twitter'])
