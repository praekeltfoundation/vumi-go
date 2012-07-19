from django.conf import settings

from go.base.tests.utils import VumiGoDjangoTestCase, declare_longcode_tags
from go.vumitools.tests.utils import CeleryTestMixIn
from go.vumitools.api import VumiApi


class DjangoGoApplicationTestCase(VumiGoDjangoTestCase, CeleryTestMixIn):

    def setUp(self):
        super(DjangoGoApplicationTestCase, self).setUp()
        self.setup_api()
        self.declare_longcode_tags()
        self.setup_celery_for_tests()

    def setup_api(self):
        self.api = VumiApi.from_config(settings.VUMI_API_CONFIG)

    def declare_longcode_tags(self):
        declare_longcode_tags(self.api)

    def acquire_all_longcode_tags(self):
        for _i in range(4):
            self.api.acquire_tag("longcode")

    def get_api_commands_sent(self):
        consumer = self.get_cmd_consumer()
        return self.fetch_cmds(consumer)
