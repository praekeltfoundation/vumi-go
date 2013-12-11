import json
from optparse import make_option
from pprint import pformat

from django.core.management.base import CommandError

from go.base.command_utils import BaseGoAccountCommand, make_command_option
from go import config


class Command(BaseGoAccountCommand):
    help = "Manage conversations."

    option_list = BaseGoAccountCommand.option_list + (
        make_command_option(
            'list', help='List the active conversations in this account.'),
        make_command_option('show', help='Display a conversation'),
        make_command_option(
            'show_config', help='Display the config for a conversation'),
        make_command_option('start', help='Start a conversation'),
        make_command_option('stop', help='Stop a conversation'),
        make_command_option('archive', help='Archive a conversation'),
        make_command_option('export', help='Export a conversation definition'),
        make_command_option('import', help='Import a conversation definition'),
        make_option('--conversation-key',
                    dest='conversation_key',
                    help='The conversation key'),
        make_option(
            '--file', dest='file', help='The file to import')
    )

    def get_conversation(self, options):
        if 'conversation_key' not in options:
            raise CommandError('Please specify a conversation key')
        conversation = self.user_api.get_wrapped_conversation(
            options['conversation_key'])
        if conversation is None:
            raise CommandError('Conversation does not exist')
        return conversation

    def handle_command_list(self, *args, **options):
        conversations = self.user_api.active_conversations()
        conversations.sort(key=lambda c: c.created_at)
        for i, c in enumerate(conversations):
            self.stdout.write("%d. %s (type: %s, key: %s)\n"
                              % (i, c.name, c.conversation_type, c.key))

    def handle_command_show(self, *args, **options):
        conversation = self.get_conversation(options)
        self.stdout.write(pformat(conversation.get_data()))
        self.stdout.write("\n")

    def handle_command_show_config(self, *args, **options):
        conversation = self.get_conversation(options)
        self.stdout.write(pformat(conversation.config))
        self.stdout.write("\n")

    def handle_command_start(self, *apps, **options):
        conversation = self.get_conversation(options)
        if conversation.archived():
            raise CommandError('Archived conversations cannot be started')
        if conversation.running() or conversation.stopping():
            raise CommandError('Conversation already running')

        self.stdout.write("Starting conversation...\n")
        conversation.start()
        self.stdout.write("Conversation started\n")

    def handle_command_stop(self, *apps, **options):
        conversation = self.get_conversation(options)
        if conversation.archived():
            raise CommandError('Archived conversations cannot be stopped')
        if conversation.stopped():
            raise CommandError('Conversation already stopped')

        self.stdout.write("Stopping conversation...\n")
        conversation.stop_conversation()
        self.stdout.write("Conversation stopped\n")

    def handle_command_archive(self, *apps, **options):
        conversation = self.get_conversation(options)
        if conversation.archived():
            raise CommandError('Archived conversations cannot be archived')
        if not conversation.stopped():
            raise CommandError('Only stopped conversations can be archived')

        self.stdout.write("Archiving conversation...\n")
        conversation.archive_conversation()
        self.stdout.write("Conversation archived\n")

    def handle_command_export(self, *apps, **options):
        conversation = self.get_conversation(options)
        self.stdout.write(json.dumps(conversation.get_data()))

    def load_file(self, options):
        if 'file' not in options:
            raise CommandError('Please specify a file to load.')
        file_name = options['file']
        return open(file_name, 'r')

    def handle_command_import(self, *apps, **options):
        raw_conv_data = json.load(self.load_file(options))
        allowed_keys = [
            'conversation_type',
            'description',
            'name',
            'config',
        ]

        new_conv_data = dict([(key, raw_conv_data[key]) for key in
                              allowed_keys])
        conversation_type = new_conv_data['conversation_type']
        if conversation_type not in config.configured_conversation_types():
            raise CommandError('Invalid conversation_type: %s' % (
                conversation_type,))
        conversation = self.user_api.new_conversation(**new_conv_data)
        self.stdout.write(json.dumps(conversation.get_data()))
