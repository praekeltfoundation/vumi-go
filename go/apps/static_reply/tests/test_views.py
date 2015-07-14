from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.apps.tests.view_helpers import AppViewsHelper
    from go.base.tests.helpers import GoDjangoTestCase


class TestStaticReplyViews(GoDjangoTestCase):
    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'static_reply'))
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

    def test_get_edit_empty_config(self):
        conv_helper = self.app_helper.create_conversation_helper()
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_get_edit_small_config(self):
        conv_helper = self.app_helper.create_conversation_helper(
            {'reply_text': 'hello'})
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hello')

    def test_edit_config(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conv = conv_helper.get_conversation()
        self.assertEqual(conv.config, {})
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'reply_text': 'hello',
        })
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        conv = conv_helper.get_conversation()
        self.assertEqual(conv.config, {'reply_text': 'hello'})
