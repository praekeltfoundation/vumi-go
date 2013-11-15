import uuid
from StringIO import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db.models.signals import post_save
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings

from twisted.python.monkey import MonkeyPatcher

from vumi.blinkenlights.metrics import MetricMessage
from vumi.tests.helpers import WorkerHelper, generate_proxies, proxyable

from go.base import amqp
from go.base import models as base_models
from go.base import utils as base_utils
from go.vumitools.tests.helpers import VumiApiHelper


class GoDjangoTestCase(TestCase):

    _cleanup_funcs = None

    def tearDown(self):
        # Run any cleanup code we've registered with .add_cleanup().
        if self._cleanup_funcs is not None:
            for cleanup, args, kw in reversed(self._cleanup_funcs):
                cleanup(*args, **kw)

    def add_cleanup(self, func, *args, **kw):
        if self._cleanup_funcs is None:
            self._cleanup_funcs = []
        self._cleanup_funcs.append((func, args, kw))


class FakeAmqpConnection(object):
    """Wrapper around an AMQP client that forwards messages.

    Command and metric messages are stored for later inspection.
    """
    def __init__(self, amqp_client):
        self._amqp = amqp_client
        self._connected = False
        self.commands = []
        self.metrics = []

    def is_connected(self):
        return self._connected

    def connect(self, dsn=None):
        self._connected = True

    def publish(self, message, exchange, routing_key):
        self._amqp.publish_raw(exchange, routing_key, message)

    def publish_command_message(self, command):
        self.commands.append(command)
        self.publish(command.to_json(), 'vumi', 'vumi.api')

    def publish_metric_message(self, metric):
        self.metrics.append(metric)
        self.publish(metric.to_json(), 'vumi', 'vumi.metrics')

    def get_commands(self):
        commands, self.commands = self.commands, []
        return commands

    def get_metrics(self):
        metrics, self.metrics = self.metrics, []
        return metrics

    def publish_metric(self, metric_name, aggregators, value, timestamp=None):
        metric_msg = MetricMessage()
        metric_msg.append((metric_name,
            tuple(sorted(agg.name for agg in aggregators)),
            [(timestamp, value)]))
        return self.publish_metric_message(metric_msg)


class DjangoVumiApiHelper(object):
    is_sync = True  # For when we're being treated like a VumiApiHelper.

    def __init__(self, worker_helper=None, use_riak=True):
        self.use_riak = use_riak
        self._vumi_helper = VumiApiHelper(is_sync=True, use_riak=use_riak)
        if worker_helper is None:
            worker_helper = WorkerHelper()
        self._worker_helper = worker_helper
        generate_proxies(self, self._vumi_helper)
        # TODO: Better/more generic way to do this patching?
        self._monkey_patches = []
        self._settings_patches = []
        self.replace_django_bits()

    def cleanup(self):
        self._vumi_helper.cleanup()
        self.restore_django_bits()
        for patch in reversed(self._settings_patches):
            patch.disable()
        for patch in reversed(self._monkey_patches):
            patch.restore()

    def replace_django_bits(self):
        # TODO: Find a nicer way to give everything the same fake redis.
        pcfg = self._vumi_helper._persistence_helper._config_overrides
        pcfg['redis_manager']['FAKE_REDIS'] = self.get_redis_manager()

        vumi_config = settings.VUMI_API_CONFIG.copy()
        vumi_config.update(pcfg)
        self.patch_settings(VUMI_API_CONFIG=vumi_config)

        has_listeners = lambda: post_save.has_listeners(get_user_model())
        assert has_listeners(), "User model has no listeners. Aborting."
        post_save.disconnect(
            sender=get_user_model(),
            dispatch_uid='go.base.models.create_user_profile')
        assert not has_listeners(), (
            "User model still has listeners. Make sure DjangoVumiApiHelper"
            " is cleaned up properly.")
        post_save.connect(
            self.create_user_profile,
            sender=get_user_model(),
            dispatch_uid='DjangoVumiApiHelper.create_user_profile')

        # We might need an AMQP connection at some point.
        broker = self._worker_helper.broker
        broker.exchange_declare('vumi', 'direct')
        self.amqp_connection = FakeAmqpConnection(broker)
        self.monkey_patch(base_utils, 'connection', self.amqp_connection)
        self.monkey_patch(amqp, 'connection', self.amqp_connection)

    def restore_django_bits(self):
        post_save.disconnect(
            sender=get_user_model(),
            dispatch_uid='DjangoVumiApiHelper.create_user_profile')
        post_save.connect(
            base_models.create_user_profile,
            sender=get_user_model(),
            dispatch_uid='go.base.models.create_user_profile')

    @proxyable
    def monkey_patch(self, obj, attribute, value):
        monkey_patch = MonkeyPatcher((obj, attribute, value))
        self._monkey_patches.append(monkey_patch)
        monkey_patch.patch()
        return monkey_patch

    @proxyable
    def get_client(self):
        client = Client()
        client.login(username='user@domain.com', password='password')
        return client

    @proxyable
    def patch_settings(self, **kwargs):
        patch = override_settings(**kwargs)
        patch.enable()
        self._settings_patches.append(patch)

    @proxyable
    def make_django_user(self):
        user = get_user_model().objects.create_user(
            email='user@domain.com', password='password')
        user.first_name = "Test"
        user.last_name = "User"
        user.save()
        user_api = base_utils.vumi_api_for_user(user)
        return self.get_user_helper(user_api.user_account_key)

    def create_user_profile(self, sender, instance, created, **kwargs):
        if not created:
            return

        if not self.use_riak:
            # Just create the account key, no actual user.
            base_models.UserProfile.objects.create(
                user=instance, user_account=uuid.uuid4())
            return

        user_helper = self.make_user(
            unicode(instance.email), enable_search=False)
        base_models.UserProfile.objects.create(
            user=instance, user_account=user_helper.account_key)
        # We add this to the helper instance rather than subclassing or
        # wrapping it because we only need the one thing.
        user_helper.get_django_user = lambda: (
            get_user_model().objects.get(pk=instance.pk))


class GoAccountCommandTestCase(GoDjangoTestCase):
    """TestCase subclass for testing management commands.

    This isn't a helper because everything it does requires asserting, which
    requires a TestCase object to call assertion methods on.
    """

    def setup_command(self, command_class):
        self.command_class = command_class
        self.vumi_helper = DjangoVumiApiHelper()
        self.add_cleanup(self.vumi_helper.cleanup)
        self.vumi_helper.setup_vumi_api()
        self.user_helper = self.vumi_helper.make_django_user()
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
        email_address = self.user_helper.get_django_user().email
        return self.command.handle(
            email_address=email_address, command=command, **options)

    def assert_command_error(self, regexp, *command, **options):
        self.assertRaisesRegexp(
            CommandError, regexp, self.call_command, *command, **options)

    def assert_command_output(self, expected_output, *command, **options):
        self.call_command(*command, **options)
        self.assertEqual(expected_output, self.command.stdout.getvalue())
