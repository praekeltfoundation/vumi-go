import uuid
from StringIO import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db.models.signals import post_save
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings

from zope.interface import implements

from vumi.tests.helpers import (
    generate_proxies, proxyable, IHelper, IHelperEnabledTestCase)

from go.base import models as base_models
from go.base import utils as base_utils
from go.vumitools.tests.helpers import VumiApiHelper, PatchHelper


class CommandIO(object):
    def __init__(self):
        self.stdout = StringIO()
        self.stderr = StringIO()


class GoDjangoTestCase(TestCase):
    implements(IHelperEnabledTestCase)

    _cleanup_funcs = None
    _patch_helper = None

    def tearDown(self):
        # Run any cleanup code we've registered with .add_cleanup().
        if self._cleanup_funcs is not None:
            for cleanup, args, kw in reversed(self._cleanup_funcs):
                cleanup(*args, **kw)

    def monkey_patch(self, obj, attribute, value):
        if self._patch_helper is None:
            self._patch_helper = self.add_helper(PatchHelper())
        self._patch_helper.monkey_patch(obj, attribute, value)

    def add_cleanup(self, func, *args, **kw):
        if self._cleanup_funcs is None:
            self._cleanup_funcs = []
        self._cleanup_funcs.append((func, args, kw))

    def add_helper(self, helper_object, *args, **kw):
        if not IHelper.providedBy(helper_object):
            raise ValueError(
                "Helper object does not provide the IHelper interface: %s" % (
                    helper_object,))
        self.add_cleanup(helper_object.cleanup)
        helper_object.setup(*args, **kw)
        return helper_object


class DjangoVumiApiHelper(object):
    implements(IHelper)

    def __init__(self, use_riak=True):
        # Note: We pass `is_sync=True` to the VumiApiHelper because a Django
        #       test case cannot be async. We define a property lower down that
        #       proxies `is_sync` from the VumiApiHelper we're wrapping so that
        #       we can be used by other helpers more easily.
        self._vumi_helper = VumiApiHelper(is_sync=True, use_riak=use_riak)
        self.use_riak = use_riak  # So create_user_profile() knows what to do.

        generate_proxies(self, self._vumi_helper)
        # TODO: Better/more generic way to do this patching?
        self._settings_patches = []

    def setup(self, setup_vumi_api=True):
        # We defer `setup_vumi_api` until we've patched Django.
        self._vumi_helper.setup(False)
        self.replace_django_bits()
        if setup_vumi_api:
            return self.setup_vumi_api()

    def cleanup(self):
        self._vumi_helper.cleanup()
        self.restore_django_bits()
        for patch in reversed(self._settings_patches):
            patch.disable()

    @property
    def is_sync(self):
        return self._vumi_helper.is_sync

    @property
    def amqp_connection(self):
        return getattr(self._vumi_helper, 'django_amqp_connection', None)

    def replace_django_bits(self):
        self._replace_settings()
        self._replace_post_save_hooks()

    def _replace_settings(self):
        # We do this redis manager hackery here because we might use it from
        # Django-land before setting (or without) up a vumi_api.
        # TODO: Find a nicer way to give everything the same fake redis.
        pcfg = self._vumi_helper._persistence_helper._config_overrides
        pcfg['redis_manager']['FAKE_REDIS'] = self.get_redis_manager()

        vumi_config = self.mk_config(settings.VUMI_API_CONFIG)
        self.patch_settings(VUMI_API_CONFIG=vumi_config)

    def _replace_post_save_hooks(self):
        has_listeners = lambda: post_save.has_listeners(get_user_model())
        assert has_listeners(), (
            "User model has no post_save listeners. Make sure"
            " DjangoVumiApiHelper is cleaned up properly in earlier tests.")
        post_save.disconnect(
            sender=get_user_model(),
            dispatch_uid='go.base.models.create_user_profile')
        assert not has_listeners(), (
            "User model still has post_save listeners. Make sure"
            " DjangoVumiApiHelper is cleaned up properly in earlier tests.")
        post_save.connect(
            self.create_user_profile,
            sender=get_user_model(),
            dispatch_uid='DjangoVumiApiHelper.create_user_profile')

    def restore_django_bits(self):
        post_save.disconnect(
            sender=get_user_model(),
            dispatch_uid='DjangoVumiApiHelper.create_user_profile')
        post_save.connect(
            base_models.create_user_profile,
            sender=get_user_model(),
            dispatch_uid='go.base.models.create_user_profile')

    @proxyable
    def get_client(self, username='user@domain.com', password='password'):
        client = Client()
        client.login(username=username, password=password)
        return client

    @proxyable
    def patch_settings(self, **kwargs):
        patch = override_settings(**kwargs)
        patch.enable()
        self._settings_patches.append(patch)

    @proxyable
    def make_django_user(self, email='user@domain.com', password='password',
                         first_name="Test", last_name="User", superuser=False):
        if superuser:
            user = get_user_model().objects.create_superuser(
                email=email, password=password)
        else:
            user = get_user_model().objects.create_user(
                email=email, password=password)
        user.first_name = first_name
        user.last_name = last_name
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
            unicode(instance.email), enable_search=True,
            django_user_pk=instance.pk)
        base_models.UserProfile.objects.create(
            user=instance, user_account=user_helper.account_key)


class GoCommandTestCase(GoDjangoTestCase):
    """TestCase subclass for testing management commands.

    This isn't a helper because everything it does requires asserting, which
    requires a TestCase object to call assertion methods on.
    """

    def setup_command(self, command_class):
        self.command_class = command_class
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user_email = self.user_helper.get_django_user().email
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
        return self.command.handle(command=command, **options)

    def assert_command_error(self, regexp, *command, **options):
        self.assertRaisesRegexp(
            CommandError, regexp, self.call_command, *command, **options)

    def assert_command_output(self, expected_output, *command, **options):
        self.call_command(*command, **options)
        self.assertEqual(expected_output, self.command.stdout.getvalue())


class GoAccountCommandTestCase(GoCommandTestCase):
    """TestCase subclass for testing management commands that require accounts.

    This isn't a helper because everything it does requires asserting, which
    requires a TestCase object to call assertion methods on.
    """

    def call_command(self, *command, **options):
        if 'email_address' not in options:
            options['email_address'] = self.user_email
        return super(GoAccountCommandTestCase, self).call_command(
            *command, **options)
