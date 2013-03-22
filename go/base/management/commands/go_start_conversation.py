from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from go.base.utils import vumi_api_for_user


class Command(BaseCommand):
    help = "Tell a conversation to start"

    LOCAL_OPTIONS = [
        make_option('--conversation-type',
            dest='conversation_type',
            help='What type of conversation to start'),
        make_option('--conversation-key',
            dest='conversation_key',
            help='What conversation to load'),
        make_option('--email-address',
            dest='email_address',
            default=False,
            help='The account to start a conversation for.'),
    ]
    option_list = BaseCommand.option_list + tuple(LOCAL_OPTIONS)

    def get_user(self, username):
        try:
            return User.objects.get(username=username)
        except (User.DoesNotExist,), e:
            raise CommandError(e)

    def get_user_api(self, username):
        return vumi_api_for_user(self.get_user(username))

    def handle(self, *apps, **options):
        email_address = options['email_address']
        if not email_address:
            raise CommandError('Please provide --email-address.')

        conversation_key = options['conversation_key']
        if not conversation_key:
            raise CommandError('Please provide --conversation-key.')

        conversation_type = options['conversation_type']
        if not conversation_type:
            raise CommandError('Please provide --conversation-type.')

        user_api = self.get_user_api(email_address)
        conversation = user_api.get_wrapped_conversation(conversation_key)
        if conversation is None:
            raise CommandError('Conversation does not exist.')
        elif conversation.conversation_type != conversation_type:
            raise CommandError('Wrong conversation type: %s vs %s' %
                                (conversation.conversation_type,
                                    conversation_type))
        elif not conversation.delivery_tag_pool:
            raise CommandError('Conversation missing delivery_tag_pool')

        handler = getattr(self, 'start_%s' % (conversation_type,),
            self.default_start_conversation)
        handler(user_api, conversation)

    def default_start_conversation(self, user_api, conversation):
        conversation.start()
