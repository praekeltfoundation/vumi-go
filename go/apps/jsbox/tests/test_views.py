import json
import logging

from go.apps.jsbox.log import LogManager
from go.apps.jsbox.view_definition import (
    JSBoxReportsView, ConversationReportsView)
from go.apps.tests.view_helpers import AppViewsHelper
from go.base.tests.helpers import GoDjangoTestCase


class TestJsBoxViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'jsbox'))
        self.client = self.app_helper.get_client()

    def test_show_stopped(self):
        conv_helper = self.app_helper.create_conversation(name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(response, '<h1>myconv</h1>')

    def test_show_running(self):
        conv_helper = self.app_helper.create_conversation(
            name=u"myconv", started=True)
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(response, '<h1>myconv</h1>')

    def setup_and_save_conversation(self, app_config):
        conv_helper = self.app_helper.create_conversation()
        # render the form
        response = self.client.get(conv_helper.get_view_url('edit'))
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
        response = self.client.post(
            conv_helper.get_view_url('edit'), form_data)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        return conv_helper.get_conversation()

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
        conv_helper = self.app_helper.create_conversation()
        campaign_key = conv_helper.get_conversation().user_account.key
        log_manager = LogManager(
            self.app_helper.vumi_helper.get_vumi_api().redis)
        for i in range(10):
            log_manager.add_log(campaign_key, conv_helper.conversation_key,
                                "test %d" % i, logging.INFO)
        response = self.client.get(conv_helper.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        for i in range(10):
            self.assertContains(response, "INFO] test %d" % i)

    def test_jsbox_empty_logs(self):
        conv_helper = self.app_helper.create_conversation()
        response = self.client.get(conv_helper.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No logs yet.")

    def test_jsbox_logs_action(self):
        conv_helper = self.app_helper.create_conversation()
        response = self.client.get(
            conv_helper.get_action_view_url('view_logs'))
        self.assertRedirects(response, conv_helper.get_view_url('jsbox_logs'))

    def test_jsbox_report_layout_building(self):
        conv_helper = self.app_helper.create_conversation()
        conversation = conv_helper.get_conversation()
        conversation.config['jsbox_app_config'] = {
            'reports': {
                'key': 'reports',
                'value': json.dumps({
                    'layout': [{
                        'type': 'diamondash.widgets.lvalue.LValueWidget',
                        'time_range': '1d',
                        'name': 'Messages Received (24h)',
                        'target': {
                            'metric_type': 'conversation',
                            'name': 'messages_received',
                        }
                    }]
                })
            }
        }

        view = JSBoxReportsView()
        layout = view.build_layout(conversation)

        self.assertEqual(layout.get_config(), [{
            'type': 'diamondash.widgets.lvalue.LValueWidget',
            'name': 'Messages Received (24h)',
            'time_range': '1d',
            'target': (
                "go.campaigns.%s.conversations.%s.messages_received.avg" %
                (conversation.user_account.key, conversation.key))
        }])

    def test_jsbox_report_layout_building_for_no_report_config(self):
        conv_helper = self.app_helper.create_conversation()
        conversation = conv_helper.get_conversation()

        default_reports_view = ConversationReportsView()
        default_layout = default_reports_view.build_layout(conversation)

        view = JSBoxReportsView()
        layout = view.build_layout(conversation)

        self.assertEqual(layout.get_config(), default_layout.get_config())
