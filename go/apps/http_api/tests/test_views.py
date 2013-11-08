
from go.apps.tests.view_helpers import AppViewHelper
from go.base.tests.utils import VumiGoDjangoTestCase


class TestHttpApiViews(VumiGoDjangoTestCase):

    use_riak = True

    def setUp(self):
        super(TestHttpApiViews, self).setUp()
        self.app_helper = AppViewHelper(self, u'http_api')
        self.add_cleanup(self.app_helper.cleanup)
        self.client = self.app_helper.get_client()

    def test_show_stopped(self):
        """
        Test showing the conversation
        """
        conv_helper = self.app_helper.create_conversation(name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        self.assertContains(response, u"<h1>myconv</h1>")

    def test_show_running(self):
        """
        Test showing the conversation
        """
        conv_helper = self.app_helper.create_conversation(
            name=u"myconv", started=True)
        response = self.client.get(conv_helper.get_view_url('show'))
        self.assertContains(response, u"<h1>myconv</h1>")

    def test_edit_view(self):
        conv_helper = self.app_helper.create_conversation()
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {})
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'http_api-api_tokens': 'token',
            'http_api-push_message_url': 'http://messages/',
            'http_api-push_event_url': 'http://events/',
            }, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        reloaded_conv = conv_helper.get_conversation()
        self.assertEqual(reloaded_conv.config, {
            'http_api': {
                'push_event_url': 'http://events/',
                'push_message_url': 'http://messages/',
                'api_tokens': ['token'],
            }
        })
