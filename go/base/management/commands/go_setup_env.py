import yaml
import os
import stat
from ConfigParser import ConfigParser

from yaml import SafeLoader
from uuid import uuid4
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.template import Context, Template

from optparse import make_option

# from foo import create_tagpool, create_user, create_transport

from vumi.persist.redis_manager import RedisManager
from vumi.persist.riak_manager import RiakManager
from vumi.components import TagpoolManager

from go.base.utils import vumi_api_for_user
from go.vumitools.api import VumiApi

# Force YAML to return unicode strings
# See: http://stackoverflow.com/questions/2890146/
SafeLoader.add_constructor(
    u'tag:yaml.org,2002:str', lambda self, node: self.construct_scalar(node))


class Command(BaseCommand):
    help = "Bootstrap a Vumi Go environment, primarily intended for testing."

    LOCAL_OPTIONS = [
        make_option(
            '--config-file',
            dest='config_file',
            default=False,
            help='Config file telling us how to connect to Riak & Redis'),
        make_option(
            '--tagpool-file',
            dest='tagpool_files',
            action='append',
            default=[],
            help='YAML file with tagpools to create.'),
        make_option(
            '--account-file',
            dest='account_files',
            action='append',
            default=[],
            help='YAML file with accounts to create.'),
        make_option(
            '--conversation-file',
            dest='conversation_files',
            action='append',
            default=[],
            help='YAML file with conversations to create.'),
        make_option(
            '--transport-file',
            dest='transport_files',
            action='append',
            default=[],
            help='YAML file with transports to create.'),
        make_option(
            '--application-file',
            dest='application_files',
            action='append',
            default=[],
            help='YAML file with applications to create.'),
        make_option(
            '--contact-group-file',
            dest='contact_group_files',
            action='append',
            default=[],
            help='YAML file with contact groups to create.'),
        make_option(
            '--dest-dir',
            dest='dest_dir',
            default='setup_env/build/',
            help='Directory to write config files to.'),
        make_option(
            '--file-name-template',
            dest='file_name_template',
            default='go_%(file_name)s.%(suffix)s',
            help='Template to use when generating config files.'),
        make_option(
            '--skip-dispatcher-configs',
            dest='write_dispatcher_configs',
            default=True,
            action='store_false',
            help='Skip writing the dispatcher configs for transports.'),
        make_option(
            '--skip-supervisord',
            dest='write_supervisord_config',
            default=True,
            action='store_false',
            help='Skip writing the supervisord.conf file'),
        make_option(
            '--supervisord-host',
            dest='supervisord_host',
            default='127.0.0.1',
            help='The host supervisord should bind to.'),
        make_option(
            '--supervisord-port',
            dest='supervisord_port',
            default='7101',
            help='The port supervisord should listen on.'),
        make_option(
            '--webapp-bind',
            dest='webapp_bind',
            default='127.0.0.1:8000',
            help='The host:addr that the Django webapp should bind to.'),
        make_option(
            '--skip-startup-script',
            dest='write_startup_script',
            default=True,
            action='store_false',
            help='Skip writing the startup_env.sh file'),
    ]
    option_list = BaseCommand.option_list + tuple(LOCAL_OPTIONS)
    auto_gen_warning = ("# This file has been automatically generated by: \n" +
                        "# %s.\n\n") % (__file__,)

    def handle(self, *apps, **options):
        config_file = options['config_file']
        if not config_file:
            raise CommandError('Please provide --config-file')

        self.config = self.read_yaml(config_file)
        self.setup_backend(self.config)
        self.file_name_template = options['file_name_template']
        self.dest_dir = options['dest_dir']
        self.supervisord_host = options['supervisord_host']
        self.supervisord_port = options['supervisord_port']
        self.webapp_bind = options['webapp_bind']

        self.contact_group_info = []
        self.conversation_info = []
        self.transport_names = []
        self.application_names = []

        for tagpool_file in options['tagpool_files']:
            self.setup_tagpools(tagpool_file)

        for account_file in options['account_files']:
            self.setup_accounts(account_file)

        for conversation_file in options['conversation_files']:
            self.setup_conversations(conversation_file)

        for contact_group_file in options['contact_group_files']:
            self.setup_contact_groups(contact_group_file)

        for transport_file in options['transport_files']:
            self.transport_names.extend(
                self.create_transport_configs(transport_file))

        for application_file in options['application_files']:
            self.application_names.extend(
                self.create_application_configs(application_file))

        if options['write_dispatcher_configs']:
            self.create_app_msg_dispatcher_config(self.application_names)
            self.write_supervisor_config_file(
                'application_message_dispatcher',
                'vumi.dispatchers.base.BaseDispatchWorker')
            self.create_vumigo_router_config(self.transport_names)
            self.write_supervisor_config_file(
                'vumigo_router',
                'vumi.dispatchers.base.BaseDispatchWorker')
            self.create_command_dispatcher_config(self.application_names)
            self.write_supervisor_config_file(
                'command_dispatcher',
                'go.vumitools.api_worker.CommandDispatcher')
            # For endpoint-based routing.
            self.create_routing_table_dispatcher_config(
                self.application_names, self.transport_names)
            self.write_supervisor_config_file(
                'routing_table_dispatcher',
                'go.vumitools.routing.AccountRoutingTableDispatcher',
                enabled=False)

        if options['write_supervisord_config']:
            self.write_supervisord_conf()
            self.create_webui_supervisord_conf()

        if options['write_startup_script']:
            self.write_startup_script()

    def setup_backend(self, config):
        self.redis = RedisManager.from_config(config['redis_manager'])
        self.riak = RiakManager.from_config(config['riak_manager'])
        # this prefix is hard coded in VumiApi
        self.tagpool = TagpoolManager(
            self.redis.sub_manager('tagpool_store'))
        self.api = VumiApi(self.riak, self.redis)

    def read_yaml(self, file_path):
        return yaml.safe_load(open(file_path, 'rb'))

    def write_yaml(self, fp, data):
        yaml.safe_dump(data, stream=fp, default_flow_style=False)

    def dump_yaml_block(self, data, indent=0):
        dumped = yaml.safe_dump(data, default_flow_style=False)
        return '\n'.join('%s%s' % ('  ' * indent, line)
                         for line in dumped.splitlines())

    def open_file(self, file_name, mode):
        "NOTE: this is only here to make testing easier"
        return open(file_name, mode)

    def render_template(self, template_name, context):
        template_dir = 'setup_env/templates/'
        with open(os.path.join(template_dir, template_name), 'r') as fp:
            template = Template(fp.read())
        return template.render(Context(context))

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

        self.stdout.write('Tag pools created: %s\n' % (
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

            if User.objects.filter(username=username).exists():
                self.stderr.write(
                    'User %s already exists. Skipping.\n' %
                    (username,))
                continue

            user = User.objects.create_user(username, username,
                                            user_info['password'])
            user.first_name = user_info.get('first_name', '')
            user.last_name = user_info.get('last_name', '')
            user.save()

            profile = user.get_profile()
            account = profile.get_user_account()

            for pool_name, max_keys in user_info['tagpools']:
                self.assign_tagpool(account, pool_name, max_keys)

            for application in user_info['applications']:
                self.assign_application(account, application)

            self.stdout.write('Account %s created\n' % (username,))

    def assign_tagpool(self, account, pool_name, max_keys):
        if pool_name not in self.tagpool.list_pools():
            raise CommandError(
                'Tagpool %s does not exist' % (pool_name,))
        permission = self.api.account_store.tag_permissions(
            uuid4().hex, tagpool=unicode(pool_name), max_keys=max_keys)
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
                'start': true,
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
            self.conversation_info.append(conv_info.copy())
            conv_info.pop('start', None)  # Don't pass to conversation.
            user = User.objects.get(username=conv_info.pop('account'))
            user_api = vumi_api_for_user(user)
            timestamp = conv_info.pop('start_timestamp', datetime.utcnow())
            conversation_key = conv_info.pop('key')
            if user_api.get_wrapped_conversation(conversation_key):
                self.stderr.write(
                    'Conversation %s already exists. Skipping.\n' % (
                        conversation_key,))
                continue

            conv = user_api.conversation_store.conversations(
                conversation_key, user_account=user_api.user_account_key,
                conversation_type=unicode(conv_info.pop('conversation_type')),
                subject=unicode(conv_info.pop('subject')),
                message=unicode(conv_info.pop('message')),
                start_timestamp=timestamp, **conv_info)
            conv.save()
            self.stdout.write('Conversation %s created\n' % (conv.key,))

    def get_transport_name(self, data):
        return data['config']['transport_name']

    def mk_filename(self, file_name, suffix):
        fn = self.file_name_template % {
            'file_name': file_name,
            'suffix': suffix,
        }
        return os.path.join(self.dest_dir, fn)

    def create_transport_configs(self, file_path):
        transports = self.read_yaml(file_path)
        for transport_name, transport_info in transports.items():
            config = transport_info['config']
            config.update({'transport_name': transport_name})
            self.write_worker_config_file(transport_name, config)
            self.write_supervisor_config_file(
                transport_name,
                transport_info['class'])
        return transports.keys()

    def write_worker_config_file(self, transport_name, config):
        fn = self.mk_filename(transport_name, 'yaml')
        with self.open_file(fn, 'w') as fp:
            fp.write(self.auto_gen_warning)
            self.write_yaml(fp, config)
        self.stdout.write('Wrote %s.\n' % (fn,))

    def create_application_configs(self, file_path):
        applications = self.read_yaml(file_path)
        application_names = []
        for application_name, application_info in applications.items():
            application_names.append(application_name)
            application_names.extend(
                application_info.get('extra_application_names', []))
            transport_name = '%s_transport' % (application_name,)
            worker_name = '%s_application' % (application_name,)
            config = application_info['config']
            # Wikipedia SMS needs to override this.
            config.setdefault('transport_name', transport_name)
            config.update({
                'worker_name': worker_name,
            })
            self.write_worker_config_file(worker_name, config)
            self.write_supervisor_config_file(
                worker_name, application_info['class'])
        return application_names

    def write_supervisor_config_file(self, program_name, worker_class,
                                     config=None, enabled=True):
        fn = self.mk_filename(program_name, 'conf')
        if not enabled:
            fn += '.disabled'
        config = config or self.mk_filename(program_name, 'yaml')
        with self.open_file(fn, 'w') as fp:
            section = "program:%s" % (program_name,)
            fp.write(self.auto_gen_warning)
            cp = ConfigParser()
            cp.add_section(section)
            cp.set(section, "command", " ".join([
                "twistd -n --pidfile=./tmp/pids/%s.pid" % (program_name,),
                "start_worker",
                "--worker-class=%s" % (worker_class,),
                "--config=%s" % (config,),
                "--vhost=%s" % self.config.get('vhost', '/develop'),
            ]))
            cp.set(section, "stdout_logfile",
                   "./logs/%(program_name)s_%(process_num)s.log")
            cp.set(section, "stderr_logfile",
                   "./logs/%(program_name)s_%(process_num)s.log")
            cp.write(fp)
        self.stdout.write('Wrote %s.\n' % (fn,))

    def create_app_msg_dispatcher_config(self, applications):
        fn = self.mk_filename('application_message_dispatcher', 'yaml')
        with self.open_file(fn, 'w') as fp:
            templ = 'application_message_dispatcher.yaml.template'
            data = self.render_template(templ, {
                'exposed_names': [
                    '%s_transport' % (app,) for app in applications],
                'conversation_mappings': dict([
                    (application, '%s_transport' % (application,)) for
                    application in applications]),
                'redis_manager': self.dump_yaml_block(
                    self.config['redis_manager'], 1),
                'riak_manager': self.dump_yaml_block(
                    self.config['riak_manager'], 1),
            })
            fp.write(self.auto_gen_warning)
            fp.write(data)

        self.stdout.write('Wrote %s.\n' % (fn,))

    def create_vumigo_router_config(self, transport_names):
        fn = self.mk_filename('vumigo_router', 'yaml')
        with self.open_file(fn, 'w') as fp:
            templ = 'vumigo_router.yaml.template'
            data = self.render_template(templ, {
                'transport_names': transport_names,
            })
            fp.write(self.auto_gen_warning)
            fp.write(data)

        self.stdout.write('Wrote %s.\n' % (fn,))

    def create_command_dispatcher_config(self, applications):
        fn = self.mk_filename('command_dispatcher', 'yaml')
        with self.open_file(fn, 'w') as fp:
            templ = 'command_dispatcher.yaml.template'
            data = self.render_template(templ, {
                'applications': applications
            })
            fp.write(self.auto_gen_warning)
            fp.write(data)

        self.stdout.write('Wrote %s.\n' % (fn,))

    def create_routing_table_dispatcher_config(self, applications, transports):
        fn = self.mk_filename('routing_table_dispatcher', 'yaml')
        with self.open_file(fn, 'w') as fp:
            templ = 'routing_table_dispatcher.yaml.template'
            data = self.render_template(templ, {
                'transport_names': transports,
                'application_names': [
                    '%s_transport' % (app,) for app in applications],
                'conversation_mappings': dict([
                    (app, '%s_transport' % (app,)) for app in applications]),
                'redis_manager': self.dump_yaml_block(
                    self.config['redis_manager'], 1),
                'riak_manager': self.dump_yaml_block(
                    self.config['riak_manager'], 1),
            })
            fp.write(self.auto_gen_warning)
            fp.write(data)

        self.stdout.write('Wrote %s.\n' % (fn,))

    def write_supervisord_conf(self):
        fn = self.mk_filename('supervisord', 'conf')
        with self.open_file(fn, 'w') as fp:
            templ = 'supervisord.conf.template'
            data = self.render_template(templ, {
                'host': self.supervisord_host,
                'port': self.supervisord_port,
                'include_files': '*.conf',
            })
            fp.write(self.auto_gen_warning)
            fp.write(data)
        self.stdout.write('Wrote %s.\n' % (fn,))

    def create_webui_supervisord_conf(self):
        program_name = 'webui'
        fn = self.mk_filename(program_name, 'conf')
        with self.open_file(fn, 'w') as fp:
            section = "program:%s" % (program_name,)
            fp.write(self.auto_gen_warning)
            cp = ConfigParser()
            cp.add_section(section)
            cp.set(
                section, "command", "./go-admin.sh runserver %s --noreload" % (
                    self.webapp_bind,))
            cp.set(section, "stdout_logfile",
                   "./logs/%(program_name)s_%(process_num)s.log")
            cp.set(section, "stderr_logfile",
                   "./logs/%(program_name)s_%(process_num)s.log")
            cp.write(fp)
        self.stdout.write('Wrote %s.\n' % (fn,))

    def setup_contact_groups(self, file_path):
        """
        Setup contact groups for specific accounts.

        :param str file_path:
            Path to the YAML file with the contact group info. Expecting to
            load the following info from it:

            [{
                'key': 'group1',
                'name': 'group1',
                'account': 'user1@go.com',
                'contacts_csv': 'path/to/contacts.csv',
            },
            {
                ...
            }]

        """
        contact_groups = self.read_yaml(file_path)
        for group_info in contact_groups:
            self.contact_group_info.append(group_info.copy())
            user = User.objects.get(username=group_info['account'])
            user_api = vumi_api_for_user(user)
            name = group_info['name'].decode('utf-8')
            account_key = user_api.user_account_key
            group = user_api.contact_store.groups(
                group_info['key'], name=name, user_account=account_key)
            group.save()
            self.stdout.write('Group %s created\n' % (group.key,))

    def write_startup_script(self):
        """
        Generate a script to import contacts and start conversations.
        """
        fn = self.mk_filename('startup_env', 'sh')
        with self.open_file(fn, 'w') as fp:
            templ = 'startup_env.sh.template'
            data = self.render_template(templ, {
                'contact_groups': self.contact_group_info,
                'conversations': self.conversation_info,
            })
            fp.write(self.auto_gen_warning)
            fp.write(data)

        os.chmod(fn, os.stat(fn).st_mode | stat.S_IEXEC)
        self.stdout.write('Wrote %s.\n' % (fn,))
