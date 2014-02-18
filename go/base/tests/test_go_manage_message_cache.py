from go.base.management.commands import go_manage_message_cache
from go.base.tests.helpers import GoCommandTestCase


class TestGoManageMessageCache(GoCommandTestCase):

    def setUp(self):
        self.setup_command(go_manage_message_cache.Command)

    def test_reconcile_conversation(self):
        conv = self.user_helper.create_conversation(u"http_api")
        expected_output = "\n".join([
            u'Processing account Test User'
            u' <user@domain.com> [test-0-user] ...',
            u'  Preforming reconcile on'
            u' batch %s ...' % conv.batch.key,
            u'done.',
            u''
        ])
        self.assert_command_output(
            expected_output, 'reconcile',
            email_address=self.user_email, conversation_key=conv.key)

    def test_reconcile_active_conversations(self):
        conv1 = self.user_helper.create_conversation(u"http_api")
        conv2 = self.user_helper.create_conversation(u"http_api")
        batch_ids = sorted([conv1.batch.key, conv2.batch.key])
        expected_output = "\n".join([
            u'Processing account Test User'
            u' <user@domain.com> [test-0-user] ...',
            u'  Preforming reconcile on'
            u' batch %s ...' % batch_ids[0],
            u'  Preforming reconcile on'
            u' batch %s ...' % batch_ids[1],
            u'done.',
            u''
        ])
        self.assert_command_output(
            expected_output, 'reconcile',
            email_address=self.user_email, active_conversations=True)
