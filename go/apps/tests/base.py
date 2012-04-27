from django.conf import settings

from vumi.tests.utils import FakeRedis

from go.base.tests.utils import VumiGoDjangoTestCase
from go.conversation.models import Conversation
from go.vumitools.tests.utils import CeleryTestMixIn


class DjangoGoApplicationTestCase(VumiGoDjangoTestCase, CeleryTestMixIn):

    def setUp(self):
        super(DjangoGoApplicationTestCase, self).setUp()
        self.setup_api()
        self.declare_longcode_tags()
        self.setup_celery_for_tests()

    def tearDown(self):
        self.teardown_api()
        super(DjangoGoApplicationTestCase, self).tearDown()

    def setup_api(self):
        self._fake_redis = FakeRedis()
        vumi_config = settings.VUMI_API_CONFIG.copy()
        vumi_config['redis_cls'] = lambda **kws: self._fake_redis
        self.patch_settings(VUMI_API_CONFIG=vumi_config)

    def teardown_api(self):
        self._fake_redis.teardown()

    def declare_longcode_tags(self):
        api = Conversation.vumi_api()
        api.declare_tags([("longcode", "default%s" % i) for i
                          in range(10001, 10001 + 4)])

    def acquire_all_longcode_tags(self):
        api = Conversation.vumi_api()
        for _i in range(4):
            api.acquire_tag("longcode")

    def get_api_commands_sent(self):
        consumer = self.get_cmd_consumer()
        return self.fetch_cmds(consumer)
