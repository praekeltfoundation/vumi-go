import yaml

from tempfile import NamedTemporaryFile
from StringIO import StringIO
from ConfigParser import ConfigParser

from django.contrib.auth import authenticate

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_setup_env
from go.base.utils import vumi_api_for_user

from mock import Mock


def tmp_yaml_file(lines):
    tmp = NamedTemporaryFile()
    tmp.write('\n'.join(lines))
    tmp.flush()
    return tmp


class FakeFile(StringIO):
    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        pass


class GoBootstrapEnvTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(GoBootstrapEnvTestCase, self).setUp()
        self.setup_api()
        self.config = self.mk_config({})

        self.command = go_setup_env.Command()
        self.command.setup_backend(self.config)
        self.tagpool = self.command.tagpool
        # do whatever setup command.handle() does manually
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()
        self.command.file_name_template = 'go_%(file_name)s.%(suffix)s'
        self.command.dest_dir = 'setup_env'
        self.command.config = {
            'redis_manager': {'key_prefix': 'test'},
            'riak_manager': {'bucket_prefix': 'test.'}
        }

        self.command.contact_group_info = []
        self.command.conversation_info = []
        self.command.router_info = []
        self.command.transport_names = []
        self.command.router_names = []
        self.command.application_names = []

        self.tagpool_file = tmp_yaml_file([
            'pools:',
            '  pool1:',
            '    tags: "[\'default%d\' % i for i in range(10)]"',
            '    metadata:',
            '      display_name: "Pool 1"',
            '  pool2:',
            '    tags: ["a", "b", "c"]',
            '    metadata:',
            '      display_name: "Pool 2"',
        ])

        self.workers_file = tmp_yaml_file([
            'transports:',
            '  sms_transport:',
            '    class: vumi.transports.telnet.TelnetServerTransport',
            '    config:',
            '      telnet_port: 8080',
            '  ussd_transport:',
            '    class: vumi.transports.telnet.TelnetServerTransport',
            '    config:',
            '      telnet_port: 8081',
            '',
            'routers:',
            '  keyword:',
            '    class: go.routers.keyword.vumi_app.KeywordRouter',
            '    config:',
            '      redis_manager: {}',
            '      riak_manager: {}',
            '',
            'applications:',
            '  bulk_message:',
            '    class: go.apps.bulk_message.vumi_app.BulkMessageApplication',
            '    config:',
            '      redis_manager: {}',
            '      riak_manager: {}',
        ])

        self.account_1_file = tmp_yaml_file([
            'account:',
            '  email: "user1@go.com"',
            '  password: foo',
            '  first_name: First',
            '  last_name: Last',
            '  applications:',
            '    - go.apps.surveys',
            '    - go.apps.bulk_message',
            '  tagpools:',
            '    - ["pool1", 10]',
            '    - ["pool2", 15]',
            '',
            'channels:',
            '  - "pool1:default0"',
            '  - "pool1:default1"',
            '',
            'conversations:',
            '  - key: "conv1"',
            '    conversation_type: survey',
            '    name: foo',
            '    config:',
            '      foo: bar',
            '  - key: conv2',
            '    conversation_type: wikipedia',
            '    name: Wikipedia',
            '    config: {}',
            '',
            'routers:',
            '  - key: "router1"',
            '    router_type: keyword',
            '    name: foo',
            '    config:',
            '      keyword_endpoint_mapping:',
            '        foo: keyword_foo',
            '',
            'routing_entries:',
            '  - ["conv1", "default", "pool1:default0", "default"]',
            '  - ["pool1:default0", "default", "conv1", "default"]',
            '',
            'contact_groups:',
            '  - key: group1',
            '    name: group1',
            '    contacts_csv: contacts.csv',
        ])

        self.account_2_file = tmp_yaml_file([
            'account:',
            '  email: "user2@go.com"',
            '  password: bar',
            '  applications:',
            '    - go.apps.bulk_message',
            '    - go.apps.jsbox',
            '  tagpools:',
            '    - ["pool1", null]',
            '    - ["pool2", null]',
            '',
            'conversations:',
            '  - key: "conversation-key-2"',
            '    conversation_type: bulk_message',
            '    name: oof',
            '    config:',
            '      oof: rab',
            '',
            'contact_groups:',
            '  - key: group2',
            '    name: group2',
            '    contacts_csv: contacts.csv',
        ])

    def read_yaml(self, yaml_file):
        return yaml.safe_load(open(yaml_file.name))

    def test_ignores_ignore_block(self):
        yaml_with_ignore = NamedTemporaryFile()
        yaml_with_ignore.write('\n'.join([
            '__ignore__:',
            '  foo: &FOO',
            '    - bar',
            '    - baz',
            'thing:',
            '  quux: *FOO',
        ]))
        yaml_with_ignore.flush()
        self.assertEqual(self.command.read_yaml(yaml_with_ignore.name), {
            'thing': {'quux': ['bar', 'baz']},
        })

    def test_tagpool_loading(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        self.assertTrue('Tag pools created: pool1, pool2' in
                            self.command.stdout.getvalue())
        self.assertEqual(self.tagpool.acquire_tag('pool2'), ('pool2', 'a'))
        self.assertEqual(self.tagpool.acquire_tag('pool2'), ('pool2', 'b'))
        self.assertEqual(self.tagpool.acquire_tag('pool2'), ('pool2', 'c'))
        self.assertEqual(self.tagpool.acquire_specific_tag(
            ('pool2', 'z')), None)
        self.assertEqual(self.tagpool.get_metadata('pool2'), {
            'display_name': 'Pool 2'
        })

        self.assertEqual(self.tagpool.acquire_specific_tag(
            ('pool1', 'default0')), ('pool1', 'default0'))
        self.assertEqual(self.tagpool.acquire_specific_tag(
            ('pool1', 'default100')), None)
        self.assertEqual(self.tagpool.get_metadata('pool1'), {
            'display_name': 'Pool 1'
        })

    def test_tagpool_loading_clears_existing_pools(self):
        self.tagpool.declare_tags([
            ("pool1", "default0"), ("pool1", "default1")
        ])
        self.tagpool.acquire_specific_tag(("pool1", "default0"))
        self.command.setup_tagpools(self.tagpool_file.name)
        self.assertTrue('Tag pools created: pool1, pool2' in
                            self.command.stdout.getvalue())
        self.assertEqual(self.tagpool.inuse_tags("pool1"), [])
        self.assertEqual(sorted(self.tagpool.free_tags("pool1")),
                         [("pool1", "default%d" % i) for i in range(10)])

    def assert_supervisor_config(self, data, program, worker_class, config):
        cp = ConfigParser()
        cp.readfp(StringIO(data))

        program_section = ':'.join(['program', program])
        self.assertTrue(cp.has_section(program_section))
        command = cp.get(program_section, 'command')
        self.assertTrue(command.startswith('twistd '))
        self.assertTrue('='.join(['--worker-class', worker_class]) in command)
        self.assertTrue('='.join(['--config', config]) in command)

    def test_create_worker_configs(self):
        self.command.create_transport_configs = Mock()
        self.command.create_router_configs = Mock()
        self.command.create_application_configs = Mock()

        self.command.create_worker_configs(self.workers_file.name)

        workers = self.read_yaml(self.workers_file)
        self.command.create_transport_configs.assert_called_once_with(
            workers['transports'])
        self.command.create_router_configs.assert_called_once_with(
            workers['routers'])
        self.command.create_application_configs.assert_called_once_with(
            workers['applications'])

    def test_create_transport_configs(self):
        fake_files = [FakeFile() for i in range(4)]
        sms_yaml, sms_conf, ussd_yaml, ussd_conf = fake_files
        self.command.open_file = Mock(side_effect=fake_files)
        transports = self.read_yaml(self.workers_file)['transports']
        self.command.create_transport_configs(transports)
        self.assertEqual(yaml.safe_load(ussd_yaml.getvalue()), {
            'telnet_port': 8081,
            'transport_name': 'ussd_transport',
        })
        self.assertEqual(yaml.safe_load(sms_yaml.getvalue()), {
            'telnet_port': 8080,
            'transport_name': 'sms_transport',
        })

        self.assert_supervisor_config(
            sms_conf.getvalue(), 'sms_transport',
            'vumi.transports.telnet.TelnetServerTransport',
            'setup_env/go_sms_transport.yaml')

        self.assert_supervisor_config(
            ussd_conf.getvalue(), 'ussd_transport',
            'vumi.transports.telnet.TelnetServerTransport',
            'setup_env/go_ussd_transport.yaml')

    def test_create_application_configs(self):
        fake_files = [FakeFile() for i in range(2)]
        app_yaml, app_conf = fake_files
        self.command.open_file = Mock(side_effect=fake_files)
        applications = self.read_yaml(self.workers_file)['applications']
        self.command.create_application_configs(applications)
        self.assertEqual(yaml.safe_load(app_yaml.getvalue()), {
            'worker_name': 'bulk_message_application',
            'transport_name': 'bulk_message_transport',
            'redis_manager': {},
            'riak_manager': {},
        })

        self.assert_supervisor_config(
            app_conf.getvalue(), 'bulk_message_application',
            'go.apps.bulk_message.vumi_app.BulkMessageApplication',
            'setup_env/go_bulk_message_application.yaml')

    def test_create_router_configs(self):
        fake_files = [FakeFile() for i in range(2)]
        router_yaml, router_conf = fake_files
        self.command.open_file = Mock(side_effect=fake_files)
        routers = self.read_yaml(self.workers_file)['routers']
        self.command.create_router_configs(routers)
        self.assertEqual(yaml.safe_load(router_yaml.getvalue()), {
            'worker_name': 'keyword_router',
            'ri_connector_name': 'keyword_router_ri',
            'ro_connector_name': 'keyword_router_ro',
            'redis_manager': {},
            'riak_manager': {},
        })

        self.assert_supervisor_config(
            router_conf.getvalue(), 'keyword_router',
            'go.routers.keyword.vumi_app.KeywordRouter',
            'setup_env/go_keyword_router.yaml')

    def test_create_routing_table_dispatcher_config(self):
        fake_file = FakeFile()
        self.command.open_file = Mock(side_effect=[fake_file])
        self.command.create_routing_table_dispatcher_config(
            ['app1', 'app2'], ['transport1', 'transport2'])
        fake_file.seek(0)
        config = yaml.safe_load(fake_file)

        self.assertEqual(config['receive_inbound_connectors'],
                         ['transport1', 'transport2'])

        self.assertEqual(config['receive_outbound_connectors'],
                         ['app1_transport', 'app2_transport'])

        self.assertEqual(config['application_connector_mapping'],
                         {'app1': 'app1_transport', 'app2': 'app2_transport'})

        self.assertEqual(config['redis_manager'], {'key_prefix': 'test'})
        self.assertEqual(config['riak_manager'], {'bucket_prefix': 'test.'})

    def test_create_command_dispatcher_config(self):
        fake_file = FakeFile()
        self.command.open_file = Mock(side_effect=[fake_file])
        self.command.create_command_dispatcher_config(
            ['app1', 'app2'], ['router1'])
        fake_file.seek(0)
        config = yaml.safe_load(fake_file)
        self.assertEqual(config['transport_name'],
            'command_dispatcher')
        self.assertEqual(config['worker_names'],
            ['app1_application', 'app2_application', 'router1_router'])

    def test_create_webui_supervisord_conf(self):
        fake_file = FakeFile()
        self.command.open_file = Mock(side_effect=[fake_file])
        self.command.webapp_bind = '[::]:8000'
        self.command.create_webui_supervisord_conf()
        fake_file.seek(0)
        webui_cp = ConfigParser()
        webui_cp.readfp(fake_file)
        self.assertTrue(webui_cp.has_section('program:webui'))
        webui_command = webui_cp.get('program:webui', 'command')
        self.assertEqual('./go-admin.sh runserver [::]:8000 --noreload',
                         webui_command)

    def test_setup_account(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        account_info = self.read_yaml(self.account_1_file)
        new_user = self.command.setup_account(account_info['account'])

        user = authenticate(username='user1@go.com', password='foo')
        self.assertEqual(user, new_user)
        self.assertTrue(user.is_active)

        user_api = vumi_api_for_user(user)
        self.assertEqual(
            set(user_api.tagpools().pools()), set(['pool1', 'pool2']))
        self.assertEqual(
            set(user_api.applications().keys()),
            set(['go.apps.bulk_message', 'go.apps.surveys']))

    def test_setup_channels(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        account_info = self.read_yaml(self.account_1_file)
        user = self.command.setup_account(account_info['account'])

        self.command.setup_channels(user, account_info['channels'])

        user_api = vumi_api_for_user(user)
        self.assertEqual(
            set([('pool1', 'default0'), ('pool1', 'default1')]),
            user_api.list_endpoints())

    def test_setup_conversations(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        account_info = self.read_yaml(self.account_1_file)
        user = self.command.setup_account(account_info['account'])

        self.command.setup_conversations(user, account_info['conversations'])

        user_api = vumi_api_for_user(user)
        [conv1, conv2] = sorted(
            user_api.active_conversations(), key=lambda c: c.key)
        self.assertEqual(conv1.key, 'conv1')
        self.assertEqual(conv1.conversation_type, 'survey')
        self.assertEqual(conv1.name, 'foo')
        self.assertEqual(conv1.config, {'foo': 'bar'})
        self.assertEqual(len(conv1.batches.keys()), 1)
        self.assertEqual(list(conv1.extra_endpoints), [])
        self.assertTrue(
            'Conversation conv1 created'
            in self.command.stdout.getvalue())

        self.assertEqual(conv2.key, 'conv2')
        self.assertEqual(conv2.conversation_type, 'wikipedia')
        self.assertEqual(conv2.name, 'Wikipedia')
        self.assertEqual(conv2.config, {})
        self.assertEqual(len(conv2.batches.keys()), 1)
        self.assertEqual(list(conv2.extra_endpoints), ['sms_content'])
        self.assertTrue(
            'Conversation conv2 created'
            in self.command.stdout.getvalue())

    def test_setup_routers(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        account_info = self.read_yaml(self.account_1_file)
        user = self.command.setup_account(account_info['account'])

        self.command.setup_routers(user, account_info['routers'])

        user_api = vumi_api_for_user(user)
        [router1] = user_api.active_routers()
        self.assertEqual(router1.key, 'router1')
        self.assertEqual(router1.router_type, 'keyword')
        self.assertEqual(router1.name, 'foo')
        self.assertEqual(router1.config, {
            'keyword_endpoint_mapping': {'foo': 'keyword_foo'},
        })
        self.assertEqual(list(router1.extra_inbound_endpoints), [])
        self.assertEqual(
            list(router1.extra_outbound_endpoints), ['keyword_foo'])
        self.assertTrue(
            'Router router1 created'
            in self.command.stdout.getvalue())

    def test_setup_contact_groups(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        account_info = self.read_yaml(self.account_1_file)
        user = self.command.setup_account(account_info['account'])

        self.command.setup_contact_groups(user, account_info['contact_groups'])

        user_api = vumi_api_for_user(user)
        [group] = user_api.list_groups()
        self.assertEqual(group.key, 'group1')
        self.assertEqual(group.name, 'group1')
        self.assertTrue(
            'Group group1 created' in self.command.stdout.getvalue())

    def test_setup_routing(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        account_info = self.read_yaml(self.account_1_file)
        user = self.command.setup_account(account_info['account'])

        self.command.setup_routing(user, account_info)

        self.assertEqual(vumi_api_for_user(user).get_routing_table(), {
            u'TRANSPORT_TAG:pool1:default0': {
                u'default': [u'CONVERSATION:survey:conv1', u'default'],
            },
            u'CONVERSATION:survey:conv1': {
                u'default': [u'TRANSPORT_TAG:pool1:default0', u'default'],
            },
        })
