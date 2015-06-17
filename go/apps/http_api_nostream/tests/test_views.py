from go.apps.tests.view_helpers import AppViewsHelper
from go.base.tests.helpers import GoDjangoTestCase


class TestHttpApiNoStreamViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'http_api_nostream'))
        self.client = self.app_helper.get_client()

    def test_show_stopped(self):
        """
        Test showing the conversation
        """
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        self.assertContains(response, u"<h1>myconv</h1>")

    def test_show_running(self):
        """
        Test showing the conversation
        """
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv", started=True)
        response = self.client.get(conv_helper.get_view_url('show'))
        self.assertContains(response, u"<h1>myconv</h1>")

    def test_edit_view(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {})
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'http_api_nostream-api_tokens': 'token',
            'http_api_nostream-push_message_url': 'http://messages/',
            'http_api_nostream-push_event_url': 'http://events/',
            'http_api_nostream-metric_store': 'foo_metric_store',
        })
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        reloaded_conv = conv_helper.get_conversation()
        self.assertEqual(reloaded_conv.config, {
            'http_api_nostream': {
                'push_event_url': 'http://events/',
                'push_message_url': 'http://messages/',
                'api_tokens': ['token'],
                'metric_store': 'foo_metric_store',
                'ignore_events': False,
                'ignore_messages': False,
                'content_length_limit': None,
            }
        })
        self.assertEqual(conversation.config, {})
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertContains(response, 'http://events/')
        self.assertContains(response, 'http://messages/')
        self.assertContains(response, 'foo_metric_store')
        self.assertEqual(response.status_code, 200)

    def test_edit_view_no_push_urls(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {})
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'http_api_nostream-api_tokens': 'token',
            'http_api_nostream-push_message_url': '',
            'http_api_nostream-push_event_url': '',
            'http_api_nostream-metric_store': 'foo_metric_store',
        })
        self.assertEqual(
            response.context['edit_forms'][0].errors, {
                'push_message_url': [
                    u'This field is required unless messages are ignored.'],
                'push_event_url': [
                    u'This field is required unless events are ignored.'],
            })

    def test_edit_view_ignore_messages(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {})
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'http_api_nostream-api_tokens': 'token',
            'http_api_nostream-push_message_url': '',
            'http_api_nostream-push_event_url': 'http://events/',
            'http_api_nostream-metric_store': 'foo_metric_store',
            'http_api_nostream-ignore_messages': 'on',
        })
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        reloaded_conv = conv_helper.get_conversation()
        self.assertEqual(reloaded_conv.config, {
            'http_api_nostream': {
                'push_event_url': 'http://events/',
                'push_message_url': None,
                'api_tokens': ['token'],
                'metric_store': 'foo_metric_store',
                'ignore_events': False,
                'ignore_messages': True,
                'content_length_limit': None,
            }
        })
        self.assertEqual(conversation.config, {})
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertContains(response, 'foo_metric_store')
        self.assertEqual(response.status_code, 200)

    def test_edit_view_ignore_events(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {})
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'http_api_nostream-api_tokens': 'token',
            'http_api_nostream-push_message_url': 'http://messages/',
            'http_api_nostream-push_event_url': '',
            'http_api_nostream-metric_store': 'foo_metric_store',
            'http_api_nostream-ignore_events': 'on',
        })
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        reloaded_conv = conv_helper.get_conversation()
        self.assertEqual(reloaded_conv.config, {
            'http_api_nostream': {
                'push_event_url': None,
                'push_message_url': 'http://messages/',
                'api_tokens': ['token'],
                'metric_store': 'foo_metric_store',
                'ignore_events': True,
                'ignore_messages': False,
                'content_length_limit': None,
            }
        })
        self.assertEqual(conversation.config, {})
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertContains(response, 'foo_metric_store')
        self.assertEqual(response.status_code, 200)

    def test_edit_view_content_length_limit(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {})
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'http_api_nostream-api_tokens': 'token',
            'http_api_nostream-push_message_url': 'http://messages/',
            'http_api_nostream-push_event_url': 'http://events/',
            'http_api_nostream-metric_store': 'foo_metric_store',
            'http_api_nostream-content_length_limit': '160',
        })
        self.assertRedirects(response, conv_helper.get_view_url('show'))

        reloaded_conv = conv_helper.get_conversation()
        self.assertEqual(reloaded_conv.config, {
            'http_api_nostream': {
                'push_event_url': 'http://events/',
                'push_message_url': 'http://messages/',
                'api_tokens': ['token'],
                'metric_store': 'foo_metric_store',
                'ignore_events': False,
                'ignore_messages': False,
                'content_length_limit': 160,
            }
        })

        # Now unset the limit
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertContains(response, '160')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'http_api_nostream-api_tokens': 'token',
            'http_api_nostream-push_message_url': 'http://messages/',
            'http_api_nostream-push_event_url': 'http://events/',
            'http_api_nostream-metric_store': 'foo_metric_store',
            'http_api_nostream-content_length_limit': '',
        })
        self.assertRedirects(response, conv_helper.get_view_url('show'))

        reloaded_conv = conv_helper.get_conversation()
        self.assertEqual(reloaded_conv.config, {
            'http_api_nostream': {
                'push_event_url': 'http://events/',
                'push_message_url': 'http://messages/',
                'api_tokens': ['token'],
                'metric_store': 'foo_metric_store',
                'ignore_events': False,
                'ignore_messages': False,
                'content_length_limit': None,
            }
        })

    def test_get_edit_view_no_config(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {})
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_get_edit_view_help(self):
        conv_helper = self.app_helper.create_conversation_helper({
            'http_api_nostream': {
                'api_tokens': ['token1234'],
            },
        })
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {})
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "\n".join([
            "  $ curl -X PUT \\",
            "       --user 'test-0-user:' \\",
            "       --data '{\"in_reply_to\": "
            "\"59b37288d8d94e42ab804158bdbf53e5\", \\",
            "                \"to_addr\": \"27761234567\", \\",
            "                \"to_addr_type\": \"msisdn\", \\",
            "                \"content\": \"This is an outgoing SMS!\"}' \\",
            "       https://go.vumi.org/api/v1/go/http_api_nostream/%s/"
            "messages.json \\",
            "       -vvv",
        ]) % conversation.key)
        self.assertContains(response, "\n".join([
            "  $ curl -X PUT \\",
            "       --user 'test-0-user:' \\",
            "       --data '[[\"total_pings\", 1200, \"MAX\"]]' \\",
            "       https://go.vumi.org/api/v1/go/http_api_nostream/%s/"
            "metrics.json \\",
            "       -vvv",
        ]) % conversation.key)
