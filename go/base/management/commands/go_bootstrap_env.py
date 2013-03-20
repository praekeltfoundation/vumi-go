import yaml
from uuid import uuid4
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from optparse import make_option

# from foo import create_tagpool, create_user, create_transport

from vumi.persist.redis_manager import RedisManager
from vumi.persist.riak_manager import RiakManager
from vumi.components import TagpoolManager

from go.base.utils import vumi_api_for_user
from go.vumitools.api import VumiApi


class Command(BaseCommand):
    help = "Bootstrap a Vumi Go environment, primarily intended for testing."

    LOCAL_OPTIONS = [
        make_option('--config-file',
            dest='config_file',
            default=False,
            help='Config file telling us how to connect to Riak & Redis'),
        make_option('--tagpool-file',
            dest='tagpool_files',
            action='append',
            default=[],
            help='YAML file with tagpools to create.'),
        make_option('--account-file',
            dest='account_files',
            action='append',
            default=[],
            help='YAML file with accounts to create.'),
        make_option('--conversation-file',
            dest='conversation_files',
            action='append',
            default=[],
            help='YAML file with conversations to create.'),
    ]
    option_list = BaseCommand.option_list + tuple(LOCAL_OPTIONS)

    def handle(self, *apps, **options):
        config_file = options['config_file']
        if not config_file:
            raise CommandError('Please provide --config-file')

        self.config = yaml.safe_load(config_file)
        self.setup_backend(self.config)

        for tagpool_file in options['tagpool_files']:
            self.setup_tagpools(tagpool_file)

        for account_file in options['account_files']:
            self.setup_accounts(account_file)

        for conversation_file in options['conversation_files']:
            self.setup_conversations(conversation_file)

    def setup_backend(self, config):
        self.redis = RedisManager.from_config(config['redis_manager'])
        self.riak = RiakManager.from_config(config['riak_manager'])
        # this prefix is hard coded in VumiApi
        self.tagpool = TagpoolManager(
            self.redis.sub_manager('tagpool_store'))
        self.api = VumiApi(self.riak, self.redis)

    def read_yaml(self, file_path):
        return yaml.safe_load(open(file_path, 'rb'))

    def setup_tagpools(self, file_path):
        """
        Create tag pools defined in a tagpool file.

        :param str file_path:
            The tagpools YAML file to load.

        """
        tp_config = self.read_yaml(file_path)
        pools = tp_config['pools']
        for pool_name, pool_data in pools.items():
            listed_tags = pool_data['tags']
            tags = (eval(listed_tags, {}, {})
                        if isinstance(listed_tags, basestring)
                        else listed_tags)
            self.tagpool.declare_tags([(pool_name, tag) for tag in tags])
            self.tagpool.set_metadata(pool_name, pool_data['metadata'])

        self.stdout.write('Tag pools created: %s' % (
            ', '.join(sorted(pools.keys())),))

    def setup_accounts(self, file_path):
        """
        Set up user accounts, including permissions for apps and tagpools.

        :param str file_path:
            A YAML file containing the user information, the apps and the
            tagpools they should have access to.

            {
                'username@vumi.org': {
                    'password': 'password',
                    'applications': ['app1', 'app2', 'app3'],
                    'tagpools': [('pool1', 10), ('pool2', 10)]
                }
            }

        """
        users = self.read_yaml(file_path)
        for username, user_info in users.items():
            user = User.objects.create_user(username, username,
                                            user_info['password'])

            profile = user.get_profile()
            account = profile.get_user_account()

            for pool_name, max_keys in user_info['tagpools']:
                self.assign_tagpool(account, pool_name, max_keys)

            for application in user_info['applications']:
                self.assign_application(account, application)

            self.stdout.write('Account %s created' % (username,))

    def assign_tagpool(self, account, pool_name, max_keys):
        if pool_name not in self.tagpool.list_pools():
            raise CommandError('Tagpool %s does not exist' %
                                (pool_name,))
        permission = self.api.account_store.tag_permissions(uuid4().hex,
            tagpool=unicode(pool_name), max_keys=max_keys)
        permission.save()

        account.tagpools.add(permission)
        account.save()
        return permission

    def assign_application(self, account, application_module):
        app_permission = self.api.account_store.application_permissions(
            uuid4().hex, application=unicode(application_module))
        app_permission.save()

        account.applications.add(app_permission)
        account.save()
        return app_permission

    def setup_conversations(self, file_path):
        """
        Setup conversations for specific accounts.

        :param str file_path:
            Path to the YAML file with the conversation info. Expecting to
            load the following info from it:

            [{
                'key': 'conversation-key-1',
                'account': 'user1@go.com',
                'conversation_type': 'survey',
                'subject': 'foo',
                'message': 'bar',
                'metadata': {
                    'foo': 'bar',
                }
            },
            {
                ...
            }]

        """
        conversations = self.read_yaml(file_path)
        for conv_info in conversations:
            user = User.objects.get(username=conv_info.pop('account'))
            user_api = vumi_api_for_user(user)
            timestamp = conv_info.pop('start_timestamp', datetime.utcnow())
            conv = user_api.conversation_store.conversations(
                conv_info.pop('key'), user_account=user_api.user_account_key,
                conversation_type=unicode(conv_info.pop('conversation_type')),
                subject=unicode(conv_info.pop('subject')),
                message=unicode(conv_info.pop('message')),
                start_timestamp=timestamp, **conv_info)
            conv.save()
            self.stdout.write('Conversation %s created' % (conv.key,))
