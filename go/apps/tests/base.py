from django.conf import settings

from vumi.tests.utils import FakeRedis

from go.base.tests.utils import VumiGoDjangoTestCase, declare_longcode_tags
from go.vumitools.tests.utils import CeleryTestMixIn
from go.vumitools.api import VumiApi


class DjangoGoApplicationTestCase(VumiGoDjangoTestCase, CeleryTestMixIn):

    def setUp(self):
        super(DjangoGoApplicationTestCase, self).setUp()
        self.setup_api()
        self.declare_longcode_tags(self.api)
        self.setup_celery_for_tests()

    def tearDown(self):
        self.teardown_api()
        super(DjangoGoApplicationTestCase, self).tearDown()

    def setup_api(self):
        self._fake_redis = FakeRedis()
        vumi_config = settings.VUMI_API_CONFIG.copy()
        vumi_config['redis_cls'] = lambda **kws: self._fake_redis
        self.patch_settings(VUMI_API_CONFIG=vumi_config)
        self.api = VumiApi(settings.VUMI_API_CONFIG)

    def teardown_api(self):
        self._fake_redis.teardown()

    def declare_longcode_tags(self):
        declare_longcode_tags(self.api)

    def acquire_all_longcode_tags(self):
        for _i in range(4):
            self.api.acquire_tag("longcode")

    def get_api_commands_sent(self):
        consumer = self.get_cmd_consumer()
        return self.fetch_cmds(consumer)
