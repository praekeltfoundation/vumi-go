from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.apps.tests.view_helpers import AppViewsHelper
    from go.base.tests.helpers import GoDjangoTestCase


class TestSequentialSendViews(GoDjangoTestCase):
    def setUp(self):
        self.app_helper = self.add_helper(
            AppViewsHelper(u'sequential_send'))
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

    def test_edit_conversation_schedule_config(self):
        conv_helper = self.app_helper.create_conversation_helper(started=True)
        self.assertEqual(conv_helper.get_conversation().config, {})
        response = self.client.post(conv_helper.get_view_url('edit'), {
            'schedule-recurring': ['daily'],
            'schedule-days': [''],
            'schedule-time': ['12:00:00'],
            'messages-TOTAL_FORMS': ['1'],
            'messages-INITIAL_FORMS': ['0'],
            'messages-MAX_NUM_FORMS': [''],
            'messages-0-message': [''],
            'messages-0-DELETE': [''],
        })
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        conversation = conv_helper.get_conversation()
        self.assertEqual(conversation.config, {
            u'messages': [],
            u'schedule': {
                u'recurring': u'daily',
                u'days': u'',
                u'time': u'12:00:00'}})
