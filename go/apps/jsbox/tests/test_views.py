import json
import logging

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.apps.jsbox.log import LogManager


class JsBoxTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'jsbox'

    def test_new_conversation(self):
        self.add_app_permission(u'go.apps.jsbox')
        self.assertEqual(len(self.conv_store.list_conversations()), 0)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.name, 'conversation name')
        self.assertEqual(conversation.description, '')
        self.assertEqual(conversation.config, {})
        self.assertRedirects(
            response, self.get_view_url('edit', conversation.key))

    def test_show_stopped(self):
        self.setup_conversation()
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)

    def test_show_running(self):
        self.setup_conversation(started=True)
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)

    def setup_and_save_conversation(self, app_config):
        self.setup_conversation()
        # render the form
        response = self.client.get(self.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        # create the form data
        form_data = {
            'jsbox-javascript': 'x = 1;',
            'jsbox-source_url': '',
            'jsbox-update_from_source': '0',
            'jsbox_app_config-TOTAL_FORMS': str(len(app_config)),
            'jsbox_app_config-INITIAL_FORMS': '0',
            'jsbox_app_config-MAX_NUM_FORMS': u''
        }
        for i, (key, cfg) in enumerate(app_config.items()):
            form_data['jsbox_app_config-%d-key' % i] = key
            form_data['jsbox_app_config-%d-value' % i] = cfg["value"]
            form_data['jsbox_app_config-%d-source_url' % i] = cfg["source_url"]
        # post the form
        response = self.client.post(self.get_view_url('edit'), form_data)
        self.assertRedirects(response, self.get_view_url('show'))
        conversation = self.get_wrapped_conv()
        return conversation

    def test_edit_conversation(self):
        conversation = self.setup_and_save_conversation({})
        self.assertEqual(conversation.config, {
            'jsbox': {
                    'javascript': 'x = 1;',
                    'source_url': '',
            },
            'jsbox_app_config': {},
        })
        self.assertEqual(list(conversation.extra_endpoints), [])

    def test_edit_conversation_with_extra_endpoints(self):
        app_config = {
            "config": {
                "value": json.dumps({
                    "sms_tag": ["foo", "bar"],
                }),
                "source_url": u"",
            }
        }
        conversation = self.setup_and_save_conversation(app_config)
        self.assertEqual(conversation.config, {
            'jsbox': {
                    'javascript': 'x = 1;',
                    'source_url': '',
            },
            'jsbox_app_config': app_config,
        })
        self.assertEqual(list(conversation.extra_endpoints), ['foo:bar'])

    def test_jsbox_logs(self):
        self.setup_conversation()
        campaign_key = self.user_api.user_account_key
        log_manager = LogManager(self.user_api.api.redis)
        for i in range(10):
            log_manager.add_log(campaign_key, self.conv_key,
                                "test %d" % i, logging.INFO)
        response = self.client.get(self.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        for i in range(10):
            self.assertContains(response, "INFO] test %d" % i)

    def test_jsbox_empty_logs(self):
        self.setup_conversation()
        response = self.client.get(self.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No logs yet.")

    def test_jsbox_logs_action(self):
        self.setup_conversation()
        response = self.client.get(self.get_action_view_url('view_logs'))
        self.assertRedirects(response, self.get_view_url('jsbox_logs'))
