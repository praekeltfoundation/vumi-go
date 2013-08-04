from StringIO import StringIO

from django.core.management.base import CommandError

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_manage_conversation


class GoManageConversationTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(GoManageConversationTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.command = go_manage_conversation.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_conv_sanity_checks(self):
        self.assertRaisesRegexp(
            CommandError,
            'User matching query does not exist', self.command.handle,
            email_address='foo@bar')
        self.assertRaisesRegexp(
            CommandError,
            'Please specify a conversation key', self.command.handle,
            email_address=self.django_user.email)
        self.assertRaisesRegexp(
            CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.django_user.email,
            conversation_key='foo')

    def do_command(self, **kwargs):
        return self.command.handle(email_address=self.django_user.email,
                                   **kwargs)

    def test_list(self):
        conv = self.create_conversation()
        self.do_command(list_conversations=True)
        self.assertEqual(
            self.command.stdout.getvalue(),
            "0. %s (type: %s, key: %s)\n" % (
                conv.name, conv.conversation_type, conv.key))

    def test_show_config(self):
        conv = self.create_conversation(config={
            'http_api': {'api_tokens': ['token']},
        })
        self.do_command(show_config=True, conversation_key=conv.key)
        self.assertEqual(
            self.command.stdout.getvalue(),
            "{u'http_api': {u'api_tokens': [u'token']}}\n")
