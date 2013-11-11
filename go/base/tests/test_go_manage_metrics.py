from go.base.utils import vumi_api_for_user
from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_manage_metrics


class GoManageApplicationCommandTestCase(VumiGoDjangoTestCase):

    def setUp(self):
        super(GoManageApplicationCommandTestCase, self).setUp()
        self.setup_api()
        self.user = self.mk_django_user()
        user_api = vumi_api_for_user(self.user)
        self.user_account_key = user_api.user_account_key
        self.redis = user_api.api.redis

    def set_metrics(self, user, disabled):
        command = go_manage_metrics.Command()
        command.handle_validated(**{
            'email-address': user.email,
            'enable': not disabled,
            'disable': disabled,
        })

    def test_enable_metrics(self):
        self.set_metrics(self.user, disabled=True)
        self.assertEqual(
            set([self.user_account_key]),
            self.redis.smembers('disabled_metrics_accounts'))

        self.set_metrics(self.user, disabled=False)
        self.assertEqual(
            set(),
            self.redis.smembers('disabled_metrics_accounts'))

    def test_disable_metrics(self):
        self.assertEqual(
            set(),
            self.redis.smembers('disabled_metrics_accounts'))

        self.set_metrics(self.user, disabled=True)

        self.assertEqual(
            set([self.user_account_key]),
            self.redis.smembers('disabled_metrics_accounts'))

    def test_enable_metrics_when_not_disabled(self):
        self.assertEqual(
            set(),
            self.redis.smembers('disabled_metrics_accounts'))

        self.set_metrics(self.user, disabled=False)

        self.assertEqual(
            set(),
            self.redis.smembers('disabled_metrics_accounts'))

    def test_disable_metrics_when_disabled(self):
        self.set_metrics(self.user, disabled=True)
        self.assertEqual(
            set([self.user_account_key]),
            self.redis.smembers('disabled_metrics_accounts'))

        self.set_metrics(self.user, disabled=True)
        self.assertEqual(
            set([self.user_account_key]),
            self.redis.smembers('disabled_metrics_accounts'))
