from go.apps.tests.view_helpers import AppViewsHelper
from go.base.tests.helpers import GoDjangoTestCase


class TestOptOutViews(GoDjangoTestCase):
    def setUp(self):
        self.app_helper = AppViewsHelper(u'opt_out')
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
