from StringIO import StringIO

from django.core.management.base import CommandError

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.management.commands import go_manage_conversation
from go.base.utils import vumi_api_for_user


class GoManageConversationTestCase(DjangoGoApplicationTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoManageConversationTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.user_api = vumi_api_for_user(self.user)
        self.profile = self.user.get_profile()
        self.command = go_manage_conversation.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()
        self.conversation = self.user_api.wrap_conversation(self.conversation)

    def test_conv_sanity_checks(self):
        self.assertRaisesRegexp(
            CommandError,
            'User matching query does not exist', self.command.handle,
            email_address='foo@bar')
        self.assertRaisesRegexp(
            CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.user.email,
            conversation_key='foo')

    def do_command(self, **kwargs):
        return self.command.handle(email_address=self.user.email,
                                   **kwargs)

    def test_list(self):
        self.do_command(list_conversations=True)
        self.assertEqual(
            self.command.stdout.getvalue(), "\n".join([
                "0. Test Conversation (type: bulk_message,"
                " key: %s)" % self.conversation.key,
            ]) + "\n")

    def test_show_config(self):
        self.conversation.set_config({
            'http_api': {
                'api_tokens': ['token'],
            }
        })
        self.conversation.save()
        self.do_command(show_config=True,
                        conversation_key=self.conversation.key)
        self.assertEqual(
            self.command.stdout.getvalue(), "\n".join([
                "{u'http_api': {u'api_tokens': [u'token']}}",
            ]) + "\n")
