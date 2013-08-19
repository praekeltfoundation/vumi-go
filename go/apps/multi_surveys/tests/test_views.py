from datetime import date
from zipfile import ZipFile
from StringIO import StringIO

from django.core import mail

from go.apps.tests.base import DjangoGoApplicationTestCase


class MultiSurveyTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'multi_survey'

    def setUp(self):
        super(MultiSurveyTestCase, self).setUp()
        self.patch_settings(
            VXPOLLS_REDIS_CONFIG=self._persist_config['redis_manager'])

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
        self.setup_conversation()
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, 'Test Conversation')

    def test_export_messages(self):
        self.setup_conversation(started=True)
        self.add_messages_to_conv(
            5, start_date=date(2012, 1, 1), time_multiplier=12, reply=True)
        conv_url = self.get_view_url('show')
        response = self.client.post(conv_url, {
            '_export_conversation_messages': True,
            })
        self.assertRedirects(response, conv_url)
        [email] = mail.outbox
        self.assertEqual(email.recipients(), [self.django_user.email])
        self.assertTrue(self.conversation.name in email.subject)
        self.assertTrue(self.conversation.name in email.body)
        [(file_name, contents, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('messages-export.csv', 'r').read()

        # 1 header, 5 sent, 5 received, 1 trailing newline == 12
        self.assertEqual(12, len(csv_contents.split('\n')))
        self.assertEqual(mime_type, 'application/zip')
