from django.conf import settings, UserSettingsHolder
from django.utils.functional import wraps
from django.test import TestCase

from vumi.persist import riak_manager

from go.vumitools.account import UserAccount
from go.vumitools.contact import Contact, ContactGroup


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


class VumiGoDjangoTestCase(TestCase):
    USE_RIAK = True

    def get_riak_manager(self, config=None):
        if config is None:
            config = settings.VUMI_API_CONFIG['riak_manager']
        manager = riak_manager.RiakManager.from_config(config)
        self._riak_managers.append(manager)
        return manager

    def setUp(self):
        self._settings_patches = []
        if self.USE_RIAK:
            self._riak_managers = []
            self.riak_manager = self.get_riak_manager()
            # We don't purge here, because fixtures put stuff in riak.

    def tearDown(self):
        if self.USE_RIAK:
            for manager in self._riak_managers:
                self._clear_bucket_properties(manager)
                manager.purge_all()
        for patch in reversed(self._settings_patches):
            patch.disable()

    def _clear_bucket_properties(self, manager):
        if not hasattr(riak_manager, 'delete_bucket_properties'):
            # This doesn't exist everywhere yet.
            return

        # If buckets are empty, they aren't listed. However, they may still
        # have properties set.
        client = manager.client
        accounts = client.bucket(manager.bucket_name(UserAccount)).get_keys()

        for account_key in accounts:
            sub_manager = manager.sub_manager(account_key)
            riak_manager.delete_bucket_properties(
                client.bucket(sub_manager.bucket_name(Contact)))
            riak_manager.delete_bucket_properties(
                client.bucket(sub_manager.bucket_name(ContactGroup)))

    def patch_settings(self, **kwargs):
        patch = override_settings(**kwargs)
        patch.enable()
        self._settings_patches.append(patch)


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
