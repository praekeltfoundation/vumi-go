from optparse import make_option

from go.base.command_utils import BaseGoAccountCommand, CommandError


class Command(BaseGoAccountCommand):
    help = "Tell a conversation to start"

    LOCAL_OPTIONS = [
        make_option('--conversation-key',
            dest='conversation_key',
            help='What conversation to load'),
    ]
    option_list = BaseGoAccountCommand.option_list + tuple(LOCAL_OPTIONS)

    def handle_no_command(self, *apps, **options):
        conversation_key = options['conversation_key']
        if not conversation_key:
            raise CommandError('Please provide --conversation-key.')

        conversation = self.user_api.get_wrapped_conversation(conversation_key)
        if conversation is None:
            raise CommandError('Conversation does not exist.')

        handler = getattr(self, 'start_%s' %
            (conversation.conversation_type,),
            self.default_start_conversation)
        handler(conversation)

    def default_start_conversation(self, conversation):
        if conversation.archived() or conversation.running():
            raise CommandError('Conversation already started.')

        conversation.start()
