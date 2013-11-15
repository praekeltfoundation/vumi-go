
from go.base.management.commands import go_manage_metrics
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoManageMetricsCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = DjangoVumiApiHelper()
        self.add_cleanup(self.vumi_helper.cleanup)
        self.vumi_helper.setup_vumi_api()
        self.user_helper = self.vumi_helper.make_django_user()
        self.redis = self.vumi_helper.get_vumi_api().redis

        self.command = go_manage_metrics.Command()

    def set_metrics(self, enabled):
        self.command.handle_validated(**{
            'email-address': self.user_helper.get_django_user().email,
            'enable': enabled,
            'disable': not enabled,
        })

    def test_enable_metrics(self):
        self.set_metrics(enabled=True)
        self.assertEqual(set([self.user_helper.account_key]),
                         self.redis.smembers('metrics_accounts'))

    def test_disable_metrics(self):
        self.set_metrics(enabled=True)
        self.assertEqual(set([self.user_helper.account_key]),
                         self.redis.smembers('metrics_accounts'))
        self.set_metrics(enabled=False)
        self.assertEqual(set(), self.redis.smembers('metrics_accounts'))

    def test_disable_metrics_when_not_enabled(self):
        self.set_metrics(enabled=False)
        self.assertEqual(set(), self.redis.smembers('metrics_accounts'))

    def test_enable_metrics_when_enabled(self):
        self.set_metrics(enabled=True)
        self.set_metrics(enabled=True)
        self.assertEqual(set([self.user_helper.account_key]),
                         self.redis.smembers('metrics_accounts'))
