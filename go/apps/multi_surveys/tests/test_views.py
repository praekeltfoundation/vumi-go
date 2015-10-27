from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.apps.tests.view_helpers import AppViewsHelper
    from go.base.tests.helpers import GoDjangoTestCase


class TestMultiSurveyViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'multi_survey'))
        self.client = self.app_helper.get_client()
        redis_config = self.app_helper.mk_config({})['redis_manager']
        self.app_helper.patch_settings(VXPOLLS_REDIS_CONFIG=redis_config)

    def add_tagpool_to_conv(self):
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        conv = self.get_wrapped_conv()
        conv.c.delivery_class = u'sms'
        conv.c.delivery_tag_pool = u'longcode'
        conv.save()

    def acquire_all_longcode_tags(self):
        for _i in range(4):
            self.user_api.acquire_tag(u"longcode")

    def test_show(self):
        """
        Test showing the conversation
        """
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, 'myconv')
