from django.test import TestCase
from django.conf import settings

from vumi.persist.riak_manager import RiakManager


class VumiGoDjangoTestCase(TestCase):
    USE_RIAK = True

    def get_riak_manager(self, config=None):
        if config is None:
            config = settings.VUMI_API_CONFIG['riak_manager']
        return RiakManager.from_config(config)

    def patch_setting(self, setting, new_value):
        self._settings_patches.append((setting, getattr(settings, setting)))
        setattr(settings, setting, new_value)

    def setUp(self):
        self._settings_patches = []
        if self.USE_RIAK:
            self.riak_manager = self.get_riak_manager()
            # We don't purge here, because fixtures put stuff in riak.

    def tearDown(self):
        if self.USE_RIAK:
            self.riak_manager.purge_all()
        for setting, old_value in reversed(self._settings_patches):
            setattr(settings, setting, old_value)
