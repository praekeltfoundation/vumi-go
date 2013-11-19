from datetime import datetime, timedelta
from StringIO import StringIO
from functools import partial
import uuid
import json

from mock import patch as mock_patch
from requests import Response
from django.conf import settings, UserSettingsHolder
from django.utils.functional import wraps
from django.test import TestCase
from django.core.paginator import Paginator
from django.test.client import Client
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model

from twisted.python.monkey import MonkeyPatcher

from vumi.tests.fake_amqp import FakeAMQPBroker
from vumi.message import TransportUserMessage, TransportEvent

from go.vumitools.tests.utils import GoPersistenceMixin, FakeAmqpConnection
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
            sender=get_user_model(),
            dispatch_uid='go.base.models.create_user_profile')
        base_models.post_save.connect(
            self.create_user_profile,
            sender=get_user_model(),
            dispatch_uid='VumiGoDjangoTestCase.create_user_profile')

        # We might need an AMQP connection at some point.
        self._amqp = FakeAMQPBroker()
        self._amqp.exchange_declare('vumi', 'direct')
        self._old_connection = base_utils.connection
        base_utils.connection = FakeAmqpConnection(self._amqp)

    def tearDown(self):
        base_utils.connection = self._old_connection
        base_models.post_save.disconnect(
            sender=get_user_model(),
            dispatch_uid='VumiGoDjangoTestCase.create_user_profile')
        base_models.post_save.connect(
            base_models.create_user_profile,
            sender=get_user_model(),
            dispatch_uid='go.base.models.create_user_profile')
        for patch in reversed(self._settings_patches):
            patch.disable()
        for patch in reversed(self._monkey_patches):
            patch.restore()
        self._persist_tearDown()

    def monkey_patch(self, obj, attribute, value):
        monkey_patch = MonkeyPatcher((obj, attribute, value))
        self._monkey_patches.append(monkey_patch)
        monkey_patch.patch()
        return monkey_patch

    def setup_client(self):
        self.client = Client()
        self.client.login(username='user@domain.com', password='password')

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
            account = self.mk_user(self.api, unicode(instance.get_username()))
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
        user = get_user_model().objects.create_user(
            'user@domain.com', 'password')
        user.first_name = "Test"
        user.last_name = "User"
        user.save()
        return get_user_model().objects.get(email='user@domain.com')

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

    def ack_message(self, msg_out):
        ack = TransportEvent(
            event_type='ack',
            user_message_id=msg_out['message_id'],
            sent_message_id=msg_out['message_id'],
            transport_type='sms',
            transport_name='sphex')
        self.api.mdb.add_event(ack)
        return ack

    def nack_message(self, msg_out, reason="nacked"):
        nack = TransportEvent(
            event_type='nack',
            user_message_id=msg_out['message_id'],
            nack_reason=reason,
        )
        self.api.mdb.add_event(nack)
        return nack

    def delivery_report_on_message(self, msg_out, status='delivered'):
        assert status in TransportEvent.DELIVERY_STATUSES
        dr = TransportEvent(
            event_type='delivery_report',
            user_message_id=msg_out['message_id'],
            delivery_status=status,
        )
        self.api.mdb.add_event(dr)
        return dr

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

            ack = self.ack_message(msg_out)
            messages.append((msg_in, msg_out, ack))
        return messages

    def add_message_to_conv(self, conversation, reply=False, sensitive=False,
                            transport_type='sms'):
        msg = TransportUserMessage(
            to_addr='9292',
            from_addr='from-addr',
            content='hello',
            transport_type=transport_type,
            transport_name='sphex')
        if sensitive:
            msg['helper_metadata']['go'] = {'sensitive': True}
        self.api.mdb.add_inbound_message(msg, batch_id=conversation.batch.key)
        if reply:
            msg_out = msg.reply('hi')
            if sensitive:
                msg_out['helper_metadata']['go'] = {'sensitive': True}
            self.api.mdb.add_outbound_message(
                msg_out, batch_id=conversation.batch.key)

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


class FakeResponse(Response):
    def __init__(self, content=None, data=None, code=200):
        super(FakeResponse, self).__init__()
        self.status_code = code

        if content is not None:
            self._content = content
        elif data is not None:
            self._content = json.dumps(data)
        else:
            self._content = ""

    @property
    def reason(self):
        return self._content


class FakeRpcResponse(FakeResponse):
    def __init__(self, id=None, result=None, error=None):
        super(FakeRpcResponse, self).__init__(
            data=self.make_rpc_data(id, result, error))

    @classmethod
    def make_rpc_data(cls, id=None, result=None, error=None):
        data = {
            'id': id,
            'jsonrpc': '2.0',
            'result': result,
        }

        if error is not None:
            data['error'] = error

        return data


class FakeServer(object):
    METHODS = [
        'get',
        'post',
        'put',
        'head',
        'patch',
        'options',
        'delete'
    ]

    def __init__(self):
        self.requests = []
        self.patchers = {}
        self.set_response(FakeResponse())

        self._patch_request()
        for method in self.METHODS:
            self._patch_request_method(method)

    def _patch_request(self):
        patcher = mock_patch('requests.request')
        self.patchers['request'] = patcher

        patched = patcher.start()
        patched.side_effect = self.stubbed_request

    def _patch_request_method(self, method):
        patcher = mock_patch('requests.%s' % method)
        self.patchers['request'] = patcher

        patched = patcher.start()
        patched.side_effect = partial(self.stubbed_request, method)

    def tear_down(self):
        for patcher in self.patchers.values():
            patcher.stop()

    def get_requests(self):
        return self.requests

    def stubbed_request(self, method, url, **kwargs):
        kwargs['url'] = url
        kwargs['method'] = method

        if 'data' in kwargs:
            kwargs['data'] = json.loads(kwargs['data'])

        self.requests.append(kwargs)
        return self.response

    def set_response(self, response):
        self.response = response
