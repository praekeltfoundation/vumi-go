import uuid

from django.conf import settings, UserSettingsHolder
from django.utils.functional import wraps
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.paginator import Paginator

from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.api import VumiApi
from go.base import models as base_models


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

    def tearDown(self):
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

    def patch_settings(self, **kwargs):
        patch = override_settings(**kwargs)
        patch.enable()
        self._settings_patches.append(patch)

    def create_user_profile(self, sender, instance, created, **kwargs):
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

    def mk_django_user(self):
        user = User.objects.create_user(
            'username', 'user@domain.com', 'password')
        user.first_name = "Test"
        user.last_name = "User"
        user.save()
        return User.objects.get(username='username')


def declare_longcode_tags(api):
    """Declare a set of long codes to the tag pool."""
    api.declare_tags([("longcode", "default%s" % i) for i
                      in range(10001, 10001 + 4)])
    api.set_pool_metadata("longcode", {
        "display_name": "Long code",
        "delivery_class": "sms",
        "transport_type": "sms",
        "server_initiated": True,
        })


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
