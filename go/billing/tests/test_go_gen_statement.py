# -*- coding: utf-8 -*-
from iso8601 import parse_date
from StringIO import StringIO

from django.core.management import call_command

from go.base.tests.helpers import (
    GoDjangoTestCase, DjangoVumiApiHelper, CommandIO)
from go.billing.models import Account, Statement


class TestGenStatement(GoDjangoTestCase):
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
            'go_gen_statement',
            stdout=cmd.stdout,
            stderr=cmd.stderr,
            **kw)
        return cmd

    def test_generate(self):
        def num_statements():
            return len(Statement.objects.filter(
                account=self.account,
                from_date=parse_date('2014-12-01'),
                to_date=parse_date('2014-12-31')))

        self.assertEqual(num_statements(), 0)

        self.run_command(
            email_address=self.user_email,
            from_date='2014-12-01',
            to_date='2014-12-31')

        self.assertEqual(num_statements(), 1)

        self.run_command(
            email_address=self.user_email,
            from_date='2014-12-01',
            to_date='2014-12-31')

        self.assertEqual(num_statements(), 2)

    def test_generate_output(self):
        cmd = self.run_command(
            email_address=self.user_email,
            from_date='2014-12-01',
            to_date='2014-12-31')

        expected = 'Statement generated for account %s from %s to %s' % (
            self.user_email,
            parse_date('2014-12-01').date(),
            parse_date('2014-12-31').date())

        self.assertEqual(cmd.stdout.getvalue().strip(), expected)
