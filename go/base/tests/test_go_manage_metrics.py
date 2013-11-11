from StringIO import StringIO

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

        self.stdout = StringIO()
        self.stderr = StringIO()

    def run_command(self, **kw):
        command = go_manage_metrics.Command()
        command.stdout = self.stdout
        command.stderr = self.stderr

        opts = {
            'list': False,
            'enable': False,
            'disable': False,
        }
        opts.update(kw)
        command.handle(**opts)

    def set_metrics(self, user, disabled):
        self.run_command(**{
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

    def test_listing(self):
        self.set_metrics(self.user, disabled=True)
        self.run_command(list=True)

        self.assertEqual(
            self.stdout.getvalue(),
            '0. Test User <user@domain.com> [%s]\n' % (
                self.user.get_profile().user_account))

    def test_listing_for_no_accounts_disabled(self):
        self.run_command(list=True)

        self.assertEqual(
            self.stderr.getvalue(),
            'No accounts have metrics disabled.\n')
