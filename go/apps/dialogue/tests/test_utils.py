from vumi.tests.helpers import VumiTestCase

from go.apps.dialogue.utils import dialogue_js_config, configured_endpoints
from go.vumitools.tests.helpers import VumiApiHelper
from go.apps.dialogue.tests.dummy_polls import simple_poll


class TestDialogueJsConfig(VumiTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(VumiApiHelper(is_sync=True))
        self.user_helper = self.vumi_helper.get_or_create_user()

    def test_config_delivery_class(self):
        poll = simple_poll()
        poll['poll_metadata']['delivery_class'] = 'twitter'

        conv = self.user_helper.create_conversation(
            u'dialogue', config={'poll': poll})

        config = dialogue_js_config(conv)
        self.assertEqual(config['delivery_class'], 'twitter')

    def test_config_endpoints(self):
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

        conv = self.user_helper.create_conversation(
            u'dialogue', config={'poll': poll})
        config = dialogue_js_config(conv)
        self.assertEqual(config['endpoints'], {
            'SMS': {'delivery_class': 'sms'},
            'Twitter': {'delivery_class': 'twitter'}
        })

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

        self.assertEqual(
            configured_endpoints({'poll': poll}),
            ['SMS', 'Twitter'])
