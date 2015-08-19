# -*- coding: utf-8 -*-
from datetime import date

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.management import call_command

    from go.base.tests.helpers import (
        GoDjangoTestCase, DjangoVumiApiHelper, CommandIO)
    from go.billing.models import Account, Statement


class TestGenStatements(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

        user = self.user_helper.get_django_user()
        self.user_email = user.email

        account_number = user.get_profile().user_account
        self.account = Account.objects.get(account_number=account_number)

    def run_command(self, **kw):
        cmd = CommandIO()
        call_command(
            'go_gen_statements',
            stdout=cmd.stdout,
            stderr=cmd.stderr,
            **kw)
        return cmd

    def test_generate(self):
        self.run_command(
            email_address=self.user_email,
            month=['2013-08', '2014-01', '2014-04'])

        statements = Statement.objects.filter(
            account=self.account,
            from_date=date(2013, 8, 1),
            to_date=date(2013, 8, 31))

        self.assertEqual(len(statements), 1)

        statements = Statement.objects.filter(
            account=self.account,
            from_date=date(2014, 1, 1),
            to_date=date(2014, 1, 31))

        self.assertEqual(len(statements), 1)

        statements = Statement.objects.filter(
            account=self.account,
            from_date=date(2014, 4, 1),
            to_date=date(2014, 4, 30))

        self.assertEqual(len(statements), 1)

    def test_generate_output(self):
        cmd = self.run_command(
            email_address=self.user_email,
            month=['2013-08', '2014-01', '2014-04'])

        self.assertEqual(cmd.stdout.getvalue(), "\n".join([
            "Generating statements for account %s..." % (self.user_email,),
            "Generated statement for 2013-08.",
            "Generated statement for 2014-01.",
            "Generated statement for 2014-04.",
            "",
        ]))
