from go.apps.tests.view_helpers import AppViewsHelper
from go.base.tests.helpers import GoDjangoTestCase


class TestWikipediaViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'wikipedia'))
        self.client = self.app_helper.get_client()

    def test_new_conversation(self):
        """Ensure that the newly created conversation has the right endpoints.
        """
        user_helper = self.app_helper.vumi_helper.get_or_create_user()
        user_helper.add_app_permission(u'go.apps.wikipedia')
        conv_store = user_helper.user_api.conversation_store

        self.assertEqual(len(conv_store.list_conversations()), 0)
        response = self.client.post(self.app_helper.get_new_view_url(), {
            'name': u"conversation name",
            'conversation_type': u"wikipedia",
        })
        self.assertEqual(len(conv_store.list_conversations()), 1)

        conversations = []
        for key in conv_store.list_conversations():
            conversations.append(conv_store.get_conversation_by_key(key))
        conversation = max(conversations, key=lambda c: c.created_at)
        conv_helper = self.app_helper.get_conversation_helper(conversation)

        self.assertEqual(conversation.name, 'conversation name')
        self.assertEqual(conversation.description, '')
        self.assertEqual(conversation.config, {})
        self.assertEqual(list(conversation.extra_endpoints), [u'sms_content'])
        self.assertRedirects(response, conv_helper.get_view_url('show'))

    def test_show_stopped(self):
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        self.assertContains(response, u"<h1>myconv</h1>")

    def test_show_running(self):
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv", started=True)
        response = self.client.get(conv_helper.get_view_url('show'))
        self.assertContains(response, u"<h1>myconv</h1>")
