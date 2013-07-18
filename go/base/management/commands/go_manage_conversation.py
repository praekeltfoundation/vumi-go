from optparse import make_option
from pprint import pformat

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from go.base.utils import vumi_api_for_user


class Command(BaseCommand):
    help = "Manage conversations."

    LOCAL_OPTIONS = [
        make_option('--email-address',
                    dest='email_address',
                    help='Email address for the Vumi Go user'),
        make_option('--conversation-key',
                    dest='conversation_key',
                    help='The conversation key'),
        make_option('--list',
                    dest='list_conversations',
                    action='store_true', default=False,
                    help='List the active conversations in this account.'),
        make_option('--show-config',
                    dest='show_config',
                    action='store_true', default=False,
                    help='Display the config for a conversation'),
    ]
    option_list = BaseCommand.option_list + tuple(LOCAL_OPTIONS)

    def handle(self, *args, **options):
        try:
            user = User.objects.get(email=options['email_address'])
        except User.DoesNotExist, e:
            raise CommandError(e)

        user_api = vumi_api_for_user(user)

        if options.get('list_conversations'):
            self.list_conversations(user_api)
            return

        if 'conversation_key' not in options:
            raise CommandError('Please specify a conversation key')
        conversation = user_api.get_wrapped_conversation(
            options['conversation_key'])
        if conversation is None:
            raise CommandError('Conversation does not exist')

        if options.get('show_config'):
            self.show_config(conversation)
        else:
            raise CommandError('Please specify an action')

    def list_conversations(self, user_api):
        conversations = user_api.active_conversations()
        conversations.sort(key=lambda c: c.created_at)
        for i, c in enumerate(conversations):
            self.stdout.write("%d. %s (type: %s, key: %s)\n"
                              % (i, c.name, c.conversation_type, c.key))

    def show_config(self, conversation):
        self.stdout.write(pformat(conversation.config))
        self.stdout.write("\n")
