from django.contrib.auth.models import User

from go.base.utils import vumi_api_for_user
from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_manage_metrics


class GoManageApplicationCommandTestCase(VumiGoDjangoTestCase):

    USE_RIAK = False

    def setUp(self):
        super(GoManageApplicationCommandTestCase, self).setUp()
        self.user = User.objects.create(username='test@user.com',
            password='password', email='test@user.com')
        user_api = vumi_api_for_user(self.user)
        self.user_account_key = user_api.user_account_key
        self.redis = user_api.api.redis

    def set_metrics(self, user, enabled):
        command = go_manage_metrics.Command()
        command.handle_validated(**{
            'email-address': user.username,
            'enable': enabled,
            'disable': not enabled,
        })

    def test_enable_metrics(self):
        self.set_metrics(self.user, enabled=True)
        self.assertEqual(set([self.user_account_key]),
                         self.redis.smembers('metrics_accounts'))

    def test_disable_metrics(self):
        self.set_metrics(self.user, enabled=True)
        self.assertEqual(set([self.user_account_key]),
                         self.redis.smembers('metrics_accounts'))
        self.set_metrics(self.user, enabled=False)
        self.assertEqual(set(), self.redis.smembers('metrics_accounts'))

    def test_disable_metrics_when_not_enabled(self):
        self.set_metrics(self.user, enabled=False)
        self.assertEqual(set(), self.redis.smembers('metrics_accounts'))

    def test_enable_metrics_when_enabled(self):
        self.set_metrics(self.user, enabled=True)
        self.set_metrics(self.user, enabled=True)
        self.assertEqual(set([self.user_account_key]),
                         self.redis.smembers('metrics_accounts'))
