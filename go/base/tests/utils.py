from django.conf import settings, UserSettingsHolder
from django.utils.functional import wraps
from django.test import TestCase

from vumi.persist.riak_manager import RiakManager


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
        print settings.VUMI_API_CONFIG
        if config is None:
            config = settings.VUMI_API_CONFIG['riak_manager']
        return RiakManager.from_config(config)

    def setUp(self):
        self._settings_patches = []
        if self.USE_RIAK:
            self.riak_manager = self.get_riak_manager()
            # We don't purge here, because fixtures put stuff in riak.

    def tearDown(self):
        if self.USE_RIAK:
            self.riak_manager.purge_all()
        for patch in reversed(self._settings_patches):
            patch.disable()

    def patch_settings(self, **kwargs):
        patch = override_settings(**kwargs)
        patch.enable()
        self._settings_patches.append(patch)
