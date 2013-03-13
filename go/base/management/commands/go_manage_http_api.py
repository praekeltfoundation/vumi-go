from uuid import uuid4
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from go.base.utils import vumi_api_for_user


class Command(BaseCommand):
    help = "manage access to an HTTP api"

    LOCAL_OPTIONS = [
        make_option('--email-address',
            dest='email_address',
            help='Email address for the Vumi Go user'),
        make_option('--conversation-key',
            dest='conversation_key',
            help='The conversation key'),
        make_option('--create-token',
            dest='create_token',
            action='store_true',
            default=False,
            help='Create a new access token for this conversation'),
        make_option('--remove-token',
            dest='remove_token',
            help='Remove an access token for this conversation'),
        make_option('--set-message-url',
            dest='set_message_url',
            help='Set a message URL'),
        make_option('--remove-message-url',
            dest='remove_message_url',
            help='Remove a message URL'),
        make_option('--set-event-url',
            dest='set_event_url',
            help='Set an event URL'),
        make_option('--remove-event-url',
            dest='remove_event_url',
            help='Remove an event URL'),
    ]
    option_list = BaseCommand.option_list + tuple(LOCAL_OPTIONS)

    def handle(self, *args, **options):
        try:
            user = User.objects.get(email=options['email_address'])
        except User.DoesNotExist, e:
            raise CommandError(e)

        user_api = vumi_api_for_user(user)
        conversation = user_api.get_wrapped_conversation(
            options['conversation_key'])

        if conversation is None:
            raise CommandError('Conversation does not exist')
        elif conversation.conversation_type != 'http_api':
            raise CommandError('Conversation is not for the HTTP API')

        if options.get('create_token'):
            self.create_token(conversation)
        elif options.get('remove_token'):
            self.remove_token(conversation, options['remove_token'])
        elif options.get('set_message_url'):
            self.set_message_url(conversation, options['set_message_url'])
        elif options.get('remove_message_url'):
            self.remove_message_url(conversation)
        elif options.get('set_event_url'):
            self.set_event_url(conversation, options['set_event_url'])
        elif options.get('remove_event_url'):
            self.remove_event_url(conversation)

    def get_metadata(self, conversation):
        metadata = conversation.get_metadata(default={})
        return metadata.get('http_api', {})

    def save_metadata(self, conversation, md):
        metadata = conversation.get_metadata(default={})
        api_metadata = metadata.get('http_api', {})
        api_metadata.update(md)
        metadata['http_api'] = api_metadata
        conversation.set_metadata(metadata)
        conversation.save()
        print conversation.metadata, conversation.key

    def create_token(self, conversation):
        token = uuid4().hex
        md = self.get_metadata(conversation)
        md.setdefault('api_tokens', []).append(token)
        self.save_metadata(conversation, md)
        self.stdout.write('Created token: %s\n' % (token,))

    def remove_token(self, conversation, token):
        md = self.get_metadata(conversation)
        tokens = md.setdefault('api_tokens', [])
        try:
            tokens.remove(token)
            self.stdout.write('Removed token %s\n' % (token,))
        except ValueError:
            raise CommandError('Token does not exist')

    def set_message_url(self, conversation, url):
        md = self.get_metadata(conversation)
        md['push_message_url'] = url
        self.save_metadata(conversation, md)
        self.stdout.write('Saved push_message_url: %s' % (url,))

    def remove_message_url(self, conversation):
        md = self.get_metadata(conversation)
        print 'got', md
        try:
            url = md.pop('push_message_url')
            self.save_metadata(conversation, md)
            self.stdout.write('Removed push_message_url: %s' % (url,))
        except KeyError:
            raise CommandError('push_message_url not set')

    def set_event_url(self, conversation, url):
        md = self.get_metadata(conversation)
        md['push_event_url'] = url
        self.save_metadata(conversation, md)
        self.stdout.write('Saved push_event_url: %s' % (url,))

    def remove_event_url(self, conversation):
        md = self.get_metadata(conversation)
        try:
            url = md.pop('push_event_url')
            self.save_metadata(conversation, md)
            self.stdout.write('Removed push_event_url: %s' % (url,))
        except KeyError:
            raise CommandError('push_event_url not set')
