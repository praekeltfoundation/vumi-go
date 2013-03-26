import yaml

from tempfile import NamedTemporaryFile
from StringIO import StringIO
from ConfigParser import ConfigParser

from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.management.commands import go_setup_env
from go.base.utils import vumi_api_for_user

from mock import Mock


def tmp_yaml_file(data):
    tmp = NamedTemporaryFile()
    yaml.dump(data, stream=tmp)
    return tmp


class FakeFile(StringIO):
    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        pass


class GoBootstrapEnvTestCase(DjangoGoApplicationTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoBootstrapEnvTestCase, self).setUp()
        self.setup_riak_fixtures()
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

        self.tagpool_file = tmp_yaml_file({
            'pools': {
                'pool1': {
                    'tags': '["default%d" % i for i in range(10)]',
                    'metadata': {
                        'display_name': 'Pool 1',
                    }
                },
                'pool2': {
                    'tags': ['a', 'b', 'c'],
                    'metadata': {
                        'display_name': 'Pool 2',
                    }
                },
            }
        })

        self.account_file = tmp_yaml_file({
            'user1@go.com': {
                'password': 'foo',
                'applications': ['go.apps.surveys', 'go.apps.bulk_message'],
                'tagpools': [
                    ['pool1', 10],
                    ['pool2', 15]
                ]
            },
            'user2@go.com': {
                'password': 'bar',
                'applications': ['go.apps.bulk_message', 'go.apps.jsbox'],
                'tagpools': [
                    ['pool1', None],
                    ['pool2', None]
                ]
            },
        })

        self.conversation_file = tmp_yaml_file([
            {
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
                'key': 'conversation-key-2',
                'account': 'user2@go.com',
                'conversation_type': 'bulk_message',
                'subject': 'oof',
                'message': 'rab',
                'metadata': {
                    'oof': 'rab',
                }
            },
        ])

        self.transports_file = tmp_yaml_file({
            'sms_transport': {
                'class': 'vumi.transports.telnet.TelnetServerTransport',
                'config': {
                    'telnet_port': 8080,
                }
            },
            'ussd_transport': {
                'class': 'vumi.transports.telnet.TelnetServerTransport',
                'config': {
                    'telnet_port': 8081,
                }

            }
        })

    def get_user_api(self, username):
        return vumi_api_for_user(User.objects.get(username=username))

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

    def test_account_loading(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        self.command.setup_accounts(self.account_file.name)

        user1 = authenticate(username='user1@go.com', password='foo')
        user2 = authenticate(username='user2@go.com', password='bar')
        self.assertTrue(all([user1.is_active, user2.is_active]))

        user1_api = vumi_api_for_user(user1)
        user1_tagpool_set = user1_api.tagpools()
        user2_api = vumi_api_for_user(user2)
        user2_tagpool_set = user2_api.tagpools()

        self.assertEqual(set(user1_tagpool_set.pools()),
            set(['pool1', 'pool2']))
        self.assertEqual(set(user2_tagpool_set.pools()),
            set(['pool1', 'pool2']))
        self.assertEqual(set(user1_api.applications().keys()),
            set(['go.apps.bulk_message', 'go.apps.surveys']))
        self.assertEqual(set(user2_api.applications().keys()),
            set(['go.apps.bulk_message', 'go.apps.jsbox']))

    def test_conversation_loading(self):
        self.command.setup_tagpools(self.tagpool_file.name)
        self.command.setup_accounts(self.account_file.name)
        self.command.setup_conversations(self.conversation_file.name)

        user1 = self.get_user_api('user1@go.com')
        user2 = self.get_user_api('user2@go.com')

        [conv1] = user1.active_conversations()
        [conv2] = user2.active_conversations()

        self.assertEqual(conv1.key, 'conversation-key-1')
        self.assertEqual(conv1.conversation_type, 'survey')
        self.assertEqual(conv1.subject, 'foo')
        self.assertEqual(conv1.message, 'bar')
        self.assertEqual(conv1.metadata, {'foo': 'bar'})

        self.assertEqual(conv2.key, 'conversation-key-2')
        self.assertEqual(conv2.conversation_type, 'bulk_message')
        self.assertEqual(conv2.subject, 'oof')
        self.assertEqual(conv2.message, 'rab')
        self.assertEqual(conv2.metadata, {'oof': 'rab'})

        self.assertTrue('Conversation conversation-key-1 created' in
                            self.command.stdout.getvalue())
        self.assertTrue('Conversation conversation-key-2 created' in
                            self.command.stdout.getvalue())

    def test_write_transport_config_file(self):
        fake_files = [FakeFile() for i in range(4)]
        sms_yaml, sms_conf, ussd_yaml, ussd_conf = fake_files
        self.command.open_file = Mock(side_effect=fake_files)
        self.command.create_transport_configs(self.transports_file.name)
        self.assertEqual(yaml.load(ussd_yaml.getvalue()), {
            'telnet_port': 8081,
            'transport_name': 'ussd_transport',
        })
        self.assertEqual(yaml.load(sms_yaml.getvalue()), {
            'telnet_port': 8080,
            'transport_name': 'sms_transport',
        })

        sms_conf.seek(0)
        sms_cp = ConfigParser()
        sms_cp.readfp(sms_conf)

        ussd_conf.seek(0)
        ussd_cp = ConfigParser()
        ussd_cp.readfp(ussd_conf)

        self.assertTrue(sms_cp.has_section('program:sms_transport'))
        self.assertTrue(ussd_cp.has_section('program:ussd_transport'))

        sms_command = sms_cp.get('program:sms_transport', 'command')
        self.assertTrue(sms_command.startswith('twistd'))
        self.assertTrue('TelnetServerTransport' in sms_command)

        ussd_command = ussd_cp.get('program:ussd_transport', 'command')
        self.assertTrue(ussd_command.startswith('twistd'))
        self.assertTrue('TelnetServerTransport' in ussd_command)

    def test_create_app_msg_dispatcher_config(self):
        fake_file = FakeFile()
        self.command.open_file = Mock(side_effect=[fake_file])
        self.command.create_app_msg_dispatcher_config([
            'app1', 'app2'])
        fake_file.seek(0)
        config = yaml.load(fake_file)
        self.assertEqual(config['exposed_names'],
            ['app1_transport', 'app2_transport'])
        self.assertEqual(config['conversation_mappings'],
            {
                'app1': 'app1_transport',
                'app2': 'app2_transport',
            })
        self.assertEqual(config['redis_manager'], {
            'key_prefix': 'test',
        })
        self.assertEqual(config['riak_manager'], {
            'bucket_prefix': 'test.',
        })

    def test_create_vumigo_router_config(self):
        fake_file = FakeFile()
        self.command.open_file = Mock(side_effect=[fake_file])
        self.command.create_vumigo_router_config([
            'transport1', 'transport2'])
        fake_file.seek(0)
        config = yaml.load(fake_file)
        self.assertEqual(config['transport_names'],
            ['transport1', 'transport2'])
        self.assertEqual(config['route_mappings'], {
            'transport1': ['vumigo_router'],
            'transport2': ['vumigo_router'],
        })
