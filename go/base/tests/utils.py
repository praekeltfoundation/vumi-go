from datetime import datetime, timedelta
from StringIO import StringIO
import uuid

from django.conf import settings, UserSettingsHolder
from django.utils.functional import wraps
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.test.client import Client
from django.core.management.base import CommandError

from twisted.python.monkey import MonkeyPatcher

from vumi.tests.fake_amqp import FakeAMQPBroker
from vumi.message import TransportUserMessage, TransportEvent

from go.vumitools.tests.utils import GoPersistenceMixin, FakeAmqpConnection
from go.vumitools.account.models import RoutingTableHelper
from go.vumitools.api import VumiApi
from go.base import models as base_models
from go.base import utils as base_utils


class override_settings(object):
    """
    Acts as either a decorator, or a context manager.  If it's a decorator it
    takes a function and returns a wrapped function.  If it's a contextmanager
    it's used with the ``with`` statement.  In either event entering/exiting
    are called before and after, respectively, the function/block is executed.
    """
    def __init__(self, **kwargs):
        self.options = kwargs
        self.wrapped = settings._wrapped

    def __enter__(self):
        self.enable()

    def __exit__(self, exc_type, exc_value, traceback):
        self.disable()

    def __call__(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return inner

    def enable(self):
        override = UserSettingsHolder(settings._wrapped)
        for key, new_value in self.options.items():
            setattr(override, key, new_value)
        settings._wrapped = override

    def disable(self):
        settings._wrapped = self.wrapped


class VumiGoDjangoTestCase(GoPersistenceMixin, TestCase):
    sync_persistence = True

    def setUp(self):
        self._persist_setUp()
        self._monkey_patches = []
        self._settings_patches = []

        # Need some hackery to make things fit together here.
        vumi_config = settings.VUMI_API_CONFIG.copy()
        self._persist_config['riak_manager'] = vumi_config['riak_manager']
        self._persist_config['redis_manager']['FAKE_REDIS'] = (
            self.get_redis_manager())
        vumi_config.update(self._persist_config)
        self.patch_settings(VUMI_API_CONFIG=vumi_config)
        base_models.post_save.disconnect(
            sender=base_models.User,
            dispatch_uid='go.base.models.create_user_profile')
        base_models.post_save.connect(
            self.create_user_profile,
            sender=base_models.User,
            dispatch_uid='VumiGoDjangoTestCase.create_user_profile')

        # We might need an AMQP connection at some point.
        self._amqp = FakeAMQPBroker()
        self._amqp.exchange_declare('vumi', 'direct')
        self._old_connection = base_utils.connection
        base_utils.connection = FakeAmqpConnection(self._amqp)

    def tearDown(self):
        base_utils.connection = self._old_connection
        base_models.post_save.disconnect(
            sender=base_models.User,
            dispatch_uid='VumiGoDjangoTestCase.create_user_profile')
        base_models.post_save.connect(
            base_models.create_user_profile,
            sender=base_models.User,
            dispatch_uid='go.base.models.create_user_profile')
        self._persist_tearDown()
        for patch in reversed(self._settings_patches):
            patch.disable()
        for patch in reversed(self._monkey_patches):
            patch.restore()

    def monkey_patch(self, obj, attribute, value):
        monkey_patch = MonkeyPatcher((obj, attribute, value))
        self._monkey_patches.append(monkey_patch)
        monkey_patch.patch()
        return monkey_patch

    def setup_client(self):
        self.client = Client()
        self.client.login(username='username', password='password')

    def patch_settings(self, **kwargs):
        patch = override_settings(**kwargs)
        patch.enable()
        self._settings_patches.append(patch)

    def create_user_profile(self, sender, instance, created, **kwargs):
        if not self.use_riak:
            if created:
                # Just create the account key, no actual user.
                base_models.UserProfile.objects.create(
                    user=instance, user_account=uuid.uuid4())
            return
        if created:
            account = self.mk_user(self.api, unicode(instance.username))
            base_models.UserProfile.objects.create(
                user=instance, user_account=account.key)
        user_api = base_models.vumi_api_for_user(instance)
        # Enable search for the contact & group stores
        user_api.contact_store.contacts.enable_search()
        user_api.contact_store.groups.enable_search()

    def setup_api(self):
        self.api = VumiApi.from_config_sync(settings.VUMI_API_CONFIG)

    def setup_user_api(self, django_user=None):
        if django_user is None:
            django_user = self.mk_django_user()
        self.django_user = django_user
        self.user_api = base_utils.vumi_api_for_user(django_user)
        self.contact_store = self.user_api.contact_store
        self.contact_store.contacts.enable_search()
        self.contact_store.groups.enable_search()
        self.conv_store = self.user_api.conversation_store
        self.router_store = self.user_api.router_store

    def mk_django_user(self):
        user = User.objects.create_user(
            'username', 'user@domain.com', 'password')
        user.first_name = "Test"
        user.last_name = "User"
        user.save()
        return User.objects.get(username='username')

    def create_conversation(self, started=False, **kwargs):
        params = {
            'conversation_type': u'test_conversation_type',
            'name': u'conversation name',
            'description': u'hello world',
            'config': {},
        }
        if started:
            params['status'] = u'running'
        params.update(kwargs)
        return self.user_api.wrap_conversation(
            self.user_api.new_conversation(**params))

    def create_router(self, started=False, **kwargs):
        params = {
            'router_type': u'test_router_type',
            'name': u'router name',
            'description': u'hello world',
            'config': {},
        }
        if started:
            params['status'] = u'running'
        params.update(kwargs)
        return self.user_api.new_router(**params)

    def add_messages_to_conv(self, message_count, conversation, reply=False,
                             ack=False, start_date=None, time_multiplier=10):
        now = start_date or datetime.now().date()
        batch_key = conversation.batch.key

        messages = []
        for i in range(message_count):
            msg_in = TransportUserMessage(
                to_addr='9292',
                from_addr='from-%s' % (i,),
                content='hello',
                transport_type='sms',
                transport_name='sphex')
            ts = now - timedelta(hours=i * time_multiplier)
            msg_in['timestamp'] = ts
            self.api.mdb.add_inbound_message(msg_in, batch_id=batch_key)
            if not reply:
                messages.append(msg_in)
                continue

            msg_out = msg_in.reply('thank you')
            msg_out['timestamp'] = ts
            self.api.mdb.add_outbound_message(msg_out, batch_id=batch_key)
            if not ack:
                messages.append((msg_in, msg_out))
                continue

            ack = TransportEvent(
                event_type='ack',
                user_message_id=msg_out['message_id'],
                sent_message_id=msg_out['message_id'],
                transport_type='sms',
                transport_name='sphex')
            self.api.mdb.add_event(ack)
            messages.append((msg_in, msg_out, ack))
        return messages

    def add_channel_to_conversation(self, conv, tag):
        # TODO: This is a duplicate of the method in
        #       go.vumitools.test.utils.GoAppWorkerTestMixin but
        #       there is no suitable common base class.
        user_account = self.user_api.get_user_account()
        rt = RoutingTableHelper(user_account.routing_table)
        rt.add_oldstyle_conversation(conv, tag)
        user_account.save()

    def declare_tags(self, pool, num_tags, metadata=None, user_select=None):
        """Declare a set of long codes to the tag pool."""
        if metadata is None:
            metadata = {
                "display_name": "Long code",
                "delivery_class": "sms",
                "transport_type": "sms",
                "server_initiated": True,
                "transport_name": "sphex",
            }
        if user_select is not None:
            metadata["user_selects_tag"] = user_select
        self.api.tpm.declare_tags([(pool, u"default%s" % i) for i
                                   in range(10001, 10001 + num_tags)])
        self.api.tpm.set_metadata(pool, metadata)

    def add_tagpool_permission(self, tagpool, max_keys=None):
        permission = self.api.account_store.tag_permissions(
            uuid.uuid4().hex, tagpool=tagpool, max_keys=max_keys)
        permission.save()
        account = self.user_api.get_user_account()
        account.tagpools.add(permission)
        account.save()

    def add_app_permission(self, application):
        permission = self.api.account_store.application_permissions(
            uuid.uuid4().hex, application=application)
        permission.save()

        account = self.user_api.get_user_account()
        account.applications.add(permission)
        account.save()


class FakeMessageStoreClient(object):

    def __init__(self, token=None, tries=2):
        self.token = token or uuid.uuid4().hex
        self.tries = tries
        self._times_called = 0

    def match(self, batch_id, direction, query):
        return self.token

    def match_results(self, batch_id, direction, token, start, stop):
        return self.results[start:stop]


class FakeMatchResult(object):
    def __init__(self, tries=1, results=[], page_size=20):
        self._times_called = 0
        self._tries = tries
        self.results = results
        self.paginator = Paginator(self, page_size)

    def __getitem__(self, value):
        return self.results.__getitem__(value)

    def count(self):
        return len(self.results)

    def is_in_progress(self):
        self._times_called += 1
        return self._tries > self._times_called


class GoAccountCommandTestCase(VumiGoDjangoTestCase):
    use_riak = True
    command_class = None

    def setUp(self):
        super(GoAccountCommandTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.command = self.command_class()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def call_command(self, *command, **options):
        # Make sure we have options for the command(s) specified
        for cmd_name in command:
            self.assertTrue(
                cmd_name in self.command.list_commands(),
                "Command '%s' has no command line option" % (cmd_name,))
        # Make sure we have options for any option keys specified
        opt_dests = set(opt.dest for opt in self.command.option_list)
        for opt_dest in options:
            self.assertTrue(
                opt_dest in opt_dests,
                "Option key '%s' has no command line option" % (opt_dest,))
        # Call the command handler
        return self.command.handle(
            email_address=self.django_user.email, command=command, **options)

    def assert_command_error(self, regexp, *command, **options):
        self.assertRaisesRegexp(
            CommandError, regexp, self.call_command, *command, **options)

    def assert_command_output(self, expected_output, *command, **options):
        self.call_command(*command, **options)
        self.assertEqual(expected_output, self.command.stdout.getvalue())
