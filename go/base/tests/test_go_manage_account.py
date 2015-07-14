from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals(), dummy_classes=['GoCommandTestCase']):
    from go.base.command_utils import make_command_option
    from go.base.management.commands import go_manage_account
    from go.base.tests.helpers import GoCommandTestCase
    from go.billing.models import Account


class TestGoManageAccount(GoCommandTestCase):

    def setUp(self):
        self.setup_command(go_manage_account.Command)

    def mk_billing_account(self):
        user = self.user_helper.get_django_user()
        return Account.objects.create(
            user=user, account_number=user.userprofile.user_account)

    def get_billing_account(self):
        user = self.user_helper.get_django_user()
        try:
            return Account.objects.get(
                account_number=user.userprofile.user_account)
        except Account.DoesNotExist:
            return None

    def setup_dummy_command(self):
        def handle_command_dummy(*args, **options):
            def dummy(user_api):
                self.command.stdout.write("  pom-pom-pom ...\n")

            self.command._apply_to_accounts(dummy)

        self.command.handle_command_dummy = handle_command_dummy
        self.command.option_list = self.command.option_list + (
            make_command_option("dummy"),)

    def test_select_individual_account(self):
        self.setup_dummy_command()
        expected_output = "\n".join([
            u'Performing dummy on account'
            u' Test User <user@domain.com> [test-0-user] ...',
            u'  pom-pom-pom ...',
            u'done.',
            u''
        ])
        self.assert_command_output(
            expected_output, 'dummy',
            email_address=self.user_email)

    def test_select_all_accounts(self):
        self.setup_dummy_command()
        self.vumi_helper.make_django_user(
            email="user-two@domain.com",
            first_name="Second", last_name="User")
        expected_output = "\n".join([
            u'Performing dummy on account'
            u' Second User <user-two@domain.com> [test-1-user] ...',
            u'  pom-pom-pom ...',
            u'done.',
            u'Performing dummy on account'
            u' Test User <user@domain.com> [test-0-user] ...',
            u'  pom-pom-pom ...',
            u'done.',
            u''
        ])
        self.assert_command_output(
            expected_output, 'dummy',
            all_accounts=True)

    def test_no_account_selected(self):
        self.setup_dummy_command()
        self.assert_command_error(
            "^Please specify either --email-address or --all-users$",
            'dummy')

    def test_dry_run(self):
        self.setup_dummy_command()
        expected_output = "\n".join([
            u'Performing dummy on account'
            u' Test User <user@domain.com> [test-0-user] ...',
            u'done.',
            u''
        ])
        self.assert_command_output(
            expected_output, 'dummy', all_accounts=True, dry_run=True)

    def test_billing_account_created(self):
        account = self.get_billing_account()
        account.delete()
        expected_output = "\n".join([
            u'Performing create_billing_account on account'
            u' Test User <user@domain.com> [test-0-user] ...',
            u'  Created billing account.',
            u'done.',
            u''
        ])
        self.assert_command_output(
            expected_output, 'create_billing_account',
            email_address=self.user_email)
        account = self.get_billing_account()
        self.assertEqual(account.user.email, self.user_email)
        self.assertEqual(account.account_number, self.user_helper.account_key)

    def test_billing_account_already_exists(self):
        initial_account = self.get_billing_account()
        expected_output = "\n".join([
            u'Performing create_billing_account on account'
            u' Test User <user@domain.com> [test-0-user] ...',
            u'  Billing account already exists.',
            u'done.',
            u''
        ])
        self.assert_command_output(
            expected_output, 'create_billing_account',
            email_address=self.user_email)
        account = self.get_billing_account()
        self.assertEqual(account.user.email, self.user_email)
        self.assertEqual(account.account_number, self.user_helper.account_key)
        self.assertEqual(account.id, initial_account.id)
