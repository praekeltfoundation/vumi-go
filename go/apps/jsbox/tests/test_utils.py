import json

from vumi.tests.helpers import VumiTestCase

from go.apps.jsbox import utils


class TestUtils(VumiTestCase):
    def test_jsbox_config_value(self):
        config = {
            'jsbox_app_config': {
                'foo': {
                    'key': 'foo',
                    'value': 'bar'
                }
            }
        }

        self.assertEqual(utils.jsbox_config_value(config, 'foo'), 'bar')

    def test_jsbox_config_value_no_value(self):
        config = {
            'jsbox_app_config': {}
        }

        self.assertEqual(utils.jsbox_config_value(config, 'foo'), None)

    def test_jsbox_config_value_no_config(self):
        self.assertEqual(utils.jsbox_config_value({}, 'foo'), None)

    def test_jsbox_js_config(self):
        config = {
            'jsbox_app_config': {
                'config': {
                    'key': 'config',
                    'value': json.dumps({'foo': 'bar'})
                }
            }
        }

        self.assertEqual(utils.jsbox_js_config(config), {'foo': 'bar'})

    def test_jsbox_js_config_no_config(self):
        config = {
            'jsbox_app_config': {
            }
        }

        self.assertEqual(utils.jsbox_js_config(config), {})
