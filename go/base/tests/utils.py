from django.conf import settings, UserSettingsHolder
from django.utils.functional import wraps
from django.test import TestCase

from go.vumitools.tests.utils import GoPersistenceMixin


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

    def tearDown(self):
        self._persist_tearDown()
        for patch in reversed(self._settings_patches):
            patch.disable()

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
