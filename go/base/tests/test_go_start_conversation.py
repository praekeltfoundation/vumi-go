from StringIO import StringIO

from django.contrib.auth.models import User
from django.core.management.base import CommandError

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.management.commands import go_start_conversation
from go.base.utils import vumi_api_for_user


class GoStartConversationTestCase(DjangoGoApplicationTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoStartConversationTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.config = self.mk_config({})
        self.command = go_start_conversation.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def get_user_api(self, username):
        return vumi_api_for_user(User.objects.get(username=username))

    def test_sanity_checks(self):
        self.assertRaisesRegexp(CommandError, 'provide --email-address',
            self.command.handle, email_address=None, conversation_key=None,
            conversation_type=None)
        self.assertRaisesRegexp(CommandError, 'provide --conversation-key',
            self.command.handle, email_address=self.user.username,
            conversation_key=None, conversation_type=None)
        self.assertRaisesRegexp(CommandError, 'provide --conversation-type',
            self.command.handle, email_address=self.user.username,
            conversation_key='foo', conversation_type=None)
        self.assertRaisesRegexp(CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.user.username,
            conversation_key='foo', conversation_type='foo')

    def test_start_conversation(self):
        print self.conversation
