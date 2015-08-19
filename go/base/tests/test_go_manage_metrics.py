from StringIO import StringIO

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.management.commands import go_manage_metrics
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoManageMetricsCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.redis = self.vumi_helper.get_vumi_api().redis

        self.stdout = StringIO()
        self.stderr = StringIO()

    def run_command(self, **kw):
        command = go_manage_metrics.Command()
        command.stdout = self.stdout
        command.stderr = self.stderr
        command.handle(**kw)

    def set_metrics(self, disabled):
        command = "disable" if disabled else "enable"
        self.run_command(**{
            'email_address': self.user_helper.get_django_user().email,
            'command': [command],
        })

    def test_enable_metrics(self):
        self.set_metrics(disabled=True)

        self.assertEqual(
            set([self.user_helper.account_key]),
            self.redis.smembers('disabled_metrics_accounts'))

        self.set_metrics(disabled=False)

        self.assertEqual(
            set(),
            self.redis.smembers('disabled_metrics_accounts'))

    def test_disable_metrics(self):
        self.assertEqual(
            set(),
            self.redis.smembers('disabled_metrics_accounts'))

        self.set_metrics(disabled=True)

        self.assertEqual(
            set([self.user_helper.account_key]),
            self.redis.smembers('disabled_metrics_accounts'))

    def test_enable_metrics_when_not_disabled(self):
        self.assertEqual(
            set(),
            self.redis.smembers('disabled_metrics_accounts'))

        self.set_metrics(disabled=False)

        self.assertEqual(
            set(),
            self.redis.smembers('disabled_metrics_accounts'))

    def test_listing(self):
        self.set_metrics(disabled=True)
        self.run_command(command=['list'])

        self.assertEqual(
            self.stdout.getvalue(),
            '0. Test User <user@domain.com> [%s]\n' % (
                self.user_helper.account_key,))

    def test_listing_for_no_accounts_disabled(self):
        self.run_command(command=['list'])

        self.assertEqual(
            self.stderr.getvalue(),
            'No accounts have metric collection disabled.\n')
