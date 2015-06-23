""" Dump URLs that can be used by cURL for downloading conversation data """

from optparse import make_option

from django.core.management.base import CommandError
from django.utils.text import slugify

from go.base.command_utils import BaseGoCommand


# We don't extend BaseGoAccountCommand since the '--email' option is used
# instead of '--email-address'
class Command(BaseGoCommand):

    help = "Dump URLs for use with cURL for downloading message data."
    DEFAULT_TEMPLATE = (
        'curl -o {file_name}-{created_at}-{status}-{direction}.json '
        '{base_url}{key}/{direction}.json?concurrency=100\n')

    option_list = BaseGoCommand.option_list + (
        make_option(
            '--email', dest='email', default=None,
            help='The user to generate export URLs for.'),
        make_option(
            '--base-url', dest='base_url', default=None,
            help='http://export-host:export-port/message_store_exporter/'),
        make_option(
            '--template', dest='template', default=DEFAULT_TEMPLATE,
            help='The template for generating the cURL.')
    )

    def handle(self, *args, **kwargs):
        self.email = kwargs['email']
        if self.email is None:
            raise CommandError('--email is mandatory.')

        self.base_url = kwargs['base_url']
        if self.base_url is None:
            raise CommandError('--base-url is mandatory.')
        self.template = kwargs['template']

        self.user, self.user_api = self.mk_user_api(self.email)

        conversation_store = self.user_api.conversation_store
        conversation_keys = conversation_store.list_conversations()
        for conversation_key in conversation_keys:
            conversation = self.user_api.get_wrapped_conversation(
                conversation_key)

            for direction in ['inbound', 'outbound']:
                self.stdout.write(
                    self.template.format(
                        file_name=slugify(conversation.name),
                        created_at=conversation.created_at.isoformat(),
                        base_url=self.base_url,
                        key=conversation.batch.key,
                        direction=direction,
                        status=(conversation.archive_status
                                if conversation.archived()
                                else conversation.get_status()),
                    )
                )
