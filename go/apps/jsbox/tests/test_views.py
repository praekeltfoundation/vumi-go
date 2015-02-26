import json
import logging

from go.apps.jsbox.log import LogManager
from go.apps.jsbox.view_definition import (
    JSBoxReportsView, ConversationReportsView)
from go.apps.tests.view_helpers import AppViewsHelper
from go.base.utils import get_conversation_view_definition
from go.base.tests.helpers import GoDjangoTestCase
from go.vumitools.api import VumiApiCommand


class TestJsBoxViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'jsbox'))
        self.client = self.app_helper.get_client()

    def setup_conversation(self, with_group=True, with_channel=True, **kw):
        groups = []
        if with_group:
            groups.append(
                self.app_helper.create_group_with_contacts(u'test_group', 0))
        channel = None
        if with_channel:
            channel = self.app_helper.create_channel(
                supports_generic_sends=True)
        return self.app_helper.create_conversation_helper(
            channel=channel, groups=groups, **kw)

    def test_action_send_jsbox_get(self):
        conv_helper = self.setup_conversation(started=True)
        response = self.client.get(
            conv_helper.get_action_view_url('send_jsbox'))
        self.assertEqual([], self.app_helper.get_api_commands_sent())
        self.assertContains(response, '<h1>Trigger push messages</h1>')

    def test_action_send_jsbox_post(self):
        conv_helper = self.setup_conversation(started=True)
        response = self.client.post(
            conv_helper.get_action_view_url('send_jsbox'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [send_jsbox_cmd] = self.app_helper.get_api_commands_sent()
        conversation = conv_helper.get_conversation()
        self.assertEqual(send_jsbox_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_jsbox', command_id=send_jsbox_cmd["command_id"],
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key))

    def test_action_send_jsbox_no_group(self):
        conv_helper = self.setup_conversation(started=True, with_group=False)
        response = self.client.post(
            conv_helper.get_action_view_url('send_jsbox'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg), "Action disabled: This action needs a contact group.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_jsbox_not_running(self):
        conv_helper = self.setup_conversation(started=False)
        response = self.client.post(
            conv_helper.get_action_view_url('send_jsbox'), {},
            follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs a running conversation.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_jsbox_no_channel(self):
        conv_helper = self.setup_conversation(started=True, with_channel=False)
        response = self.client.post(
            conv_helper.get_action_view_url('send_jsbox'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs channels capable"
            " of sending messages attached to this conversation.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_show_stopped(self):
        conv_helper = self.setup_conversation(started=False, name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(response, '<h1>myconv</h1>')
        self.assertNotContains(
            response, conv_helper.get_action_view_url('send_jsbox'))

    def test_show_running(self):
        conv_helper = self.setup_conversation(started=True, name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(response, '<h1>myconv</h1>')
        self.assertContains(response,
                            conv_helper.get_action_view_url('send_jsbox'))

    def setup_and_save_conversation(self, app_config):
        conv_helper = self.setup_conversation()
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

    def test_edit_conversation_with_v2_extra_endpoints(self):
        app_config = {
            "config": {
                "value": json.dumps({
                    "endpoints": {
                        "endpoint1": {},
                        "endpoint2": {},
                    },
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
        self.assertEqual(list(conversation.extra_endpoints),
                         ['endpoint1', 'endpoint2'])

    def test_edit_conversation_with_v1_extra_endpoints(self):
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
        conv_helper = self.setup_conversation()
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
        conv_helper = self.setup_conversation()
        response = self.client.get(conv_helper.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No logs yet.")

    def test_jsbox_logs_action(self):
        conv_helper = self.setup_conversation()
        response = self.client.get(
            conv_helper.get_action_view_url('view_logs'))
        self.assertRedirects(response, conv_helper.get_view_url('jsbox_logs'))

    def test_jsbox_report_layout_building(self):
        conv_helper = self.setup_conversation()
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
        conv_helper = self.setup_conversation()
        conversation = conv_helper.get_conversation()

        view_def = get_conversation_view_definition(
            conversation.conversation_type)
        default_reports_view = ConversationReportsView(view_def=view_def)
        default_layout = default_reports_view.build_layout(conversation)

        view = JSBoxReportsView(view_def=view_def)
        layout = view.build_layout(conversation)

        self.assertEqual(layout.get_config(), default_layout.get_config())
