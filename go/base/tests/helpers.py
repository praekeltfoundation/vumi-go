import uuid

from django.conf import settings, UserSettingsHolder
from django.contrib.auth import get_user_model
from django.test.client import Client
from django.utils.functional import wraps

from twisted.python.monkey import MonkeyPatcher

from vumi.tests.helpers import WorkerHelper, generate_proxies, proxyable

from go.base import models as base_models
from go.base import utils as base_utils
from go.vumitools.tests.helpers import VumiApiHelper
from go.vumitools.tests.utils import FakeAmqpConnection


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


class DjangoVumiApiHelper(object):
    def __init__(self, test_case, worker_helper=None):
        self._test_case = test_case
        self._vumi_helper = VumiApiHelper(test_case)
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
        # Need some hackery to make things fit together here.
        vumi_config = settings.VUMI_API_CONFIG.copy()
        persist_config = self._test_case._persist_config
        persist_config['riak_manager'] = vumi_config['riak_manager']
        persist_config['redis_manager']['FAKE_REDIS'] = (
            self._test_case.get_redis_manager())
        vumi_config.update(persist_config)
        self.patch_settings(VUMI_API_CONFIG=vumi_config)

        has_listeners = lambda: base_models.post_save.has_listeners(
            base_models.User)
        assert has_listeners(), "User model has no listeners. Aborting."
        base_models.post_save.disconnect(
            sender=base_models.User,
            dispatch_uid='go.base.models.create_user_profile')
        assert not has_listeners(), (
            "User model still has listeners. Make sure DjangoVumiApiHelper"
            " is cleaned up properly.")
        base_models.post_save.connect(
            self.create_user_profile,
            sender=base_models.User,
            dispatch_uid='DjangoVumiApiHelper.create_user_profile')

        # We might need an AMQP connection at some point.
        broker = self._worker_helper.broker
        broker.exchange_declare('vumi', 'direct')
        self.monkey_patch(base_utils, 'connection', FakeAmqpConnection(broker))

    def restore_django_bits(self):
        base_models.post_save.disconnect(
            sender=base_models.User,
            dispatch_uid='DjangoVumiApiHelper.create_user_profile')
        base_models.post_save.connect(
            base_models.create_user_profile,
            sender=base_models.User,
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
        client.login(username='username', password='password')
        return client

    @proxyable
    def patch_settings(self, **kwargs):
        patch = override_settings(**kwargs)
        patch.enable()
        self._settings_patches.append(patch)

    @proxyable
    def make_django_user(self):
        user = get_user_model().objects.create_user(
            'username', 'user@domain.com', 'password')
        user.first_name = "Test"
        user.last_name = "User"
        user.save()
        user_api = base_utils.vumi_api_for_user(user)
        return self.get_user_helper(user_api.user_account_key)

    def create_user_profile(self, sender, instance, created, **kwargs):
        if not created:
            return

        if not self._test_case.use_riak:
            # Just create the account key, no actual user.
            base_models.UserProfile.objects.create(
                user=instance, user_account=uuid.uuid4())
            return

        user_helper = self.make_user(
            unicode(instance.username), enable_search=False)
        base_models.UserProfile.objects.create(
            user=instance, user_account=user_helper.account_key)
        # We add this to the helper instance rather than subclassing or
        # wrapping it because we only need the one thing.
        user_helper.get_django_user = lambda: (
            get_user_model().objects.get(pk=instance.pk))
