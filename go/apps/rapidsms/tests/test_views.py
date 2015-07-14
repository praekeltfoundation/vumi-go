from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.apps.tests.view_helpers import AppViewsHelper
    from go.base.tests.helpers import GoDjangoTestCase


class TestRapidSmsViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'rapidsms'))
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
            'rapidsms-rapidsms_url': 'http://www.example.com/',
            'rapidsms-rapidsms_username': 'rapid_user',
            'rapidsms-rapidsms_password': 'rapid_pass',
            'rapidsms-rapidsms_auth_method': 'basic',
            'rapidsms-rapidsms_http_method': 'POST',
            'rapidsms-allowed_endpoints': 'default',
            'auth_tokens-auth_token': 'auth-token-1',
        }, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        reloaded_conv = conv_helper.get_conversation()
        self.assertEqual(reloaded_conv.config, {
            'rapidsms': {
                u'allowed_endpoints': [u'default'],
                u'rapidsms_auth_method': u'basic',
                u'rapidsms_http_method': u'POST',
                u'rapidsms_password': u'rapid_pass',
                u'rapidsms_url': u'http://www.example.com/',
                u'rapidsms_username': u'rapid_user',
            },
            'auth_tokens': {
                u'api_tokens': [u'auth-token-1'],
            },
        })
