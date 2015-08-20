from datetime import date
from zipfile import ZipFile
from StringIO import StringIO

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core import mail

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

    def test_export_messages(self):
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv")
        msgs = conv_helper.add_stored_inbound(
            5, start_date=date(2012, 1, 1), time_multiplier=12)
        conversation = conv_helper.get_conversation()
        conv_helper.add_stored_replies(msgs)
        export_url = conv_helper.get_view_url('export_messages')
        message_url = conv_helper.get_view_url('message_list')
        response = self.client.post(export_url)
        self.assertRedirects(response, message_url)
        [email] = mail.outbox
        django_user = self.app_helper.get_or_create_user().get_django_user()
        self.assertEqual(email.recipients(), [django_user.email])
        self.assertTrue(conversation.name in email.subject)
        self.assertTrue(conversation.name in email.body)
        [(file_name, contents, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('messages-export.csv', 'r').read()

        # 1 header, 5 sent, 5 received, 1 trailing newline == 12
        self.assertEqual(12, len(csv_contents.split('\n')))
        self.assertEqual(mime_type, 'application/zip')
