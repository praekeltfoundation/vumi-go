from django.test import TestCase
from vumi.tests.utils import FakeRedis
from django.conf import settings
from go.conversation.models import Conversation
from go.vumitools.tests.utils import CeleryTestMixIn


class DjangoGoApplicationTestCase(TestCase, CeleryTestMixIn):

    def setUp(self):
        self.setup_api()
        self.declare_longcode_tags()
        self.setup_celery_for_tests()

    def tearDown(self):
        self.teardown_api()

    def setup_api(self):
        self._fake_redis = FakeRedis()
        self._old_vumi_api_config = settings.VUMI_API_CONFIG
        settings.VUMI_API_CONFIG = {
            'redis_cls': lambda **kws: self._fake_redis,
            'message_store': {},
            'message_sender': {},
            }

    def teardown_api(self):
        settings.VUMI_API_CONFIG = self._old_vumi_api_config
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
