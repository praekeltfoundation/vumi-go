# -*- coding: utf-8 -*-

from datetime import datetime

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.management import call_command

    from go.base.s3utils import Bucket
    from go.base.tests.helpers import (
        GoDjangoTestCase, DjangoVumiApiHelper, CommandIO)
    from go.base.tests.s3_helpers import S3Helper
    from go.billing.models import Account, Transaction, TransactionArchive
    from go.billing.tests.helpers import (
        mk_statement, mk_transaction, this_month)


class TestArchiveTransactions(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.s3_helper = self.add_helper(S3Helper(self.vumi_helper))
        self.user_helper = self.vumi_helper.make_django_user()

        user = self.user_helper.get_django_user()
        self.user_email = user.email

        account_number = user.get_profile().user_account
        self.account = Account.objects.get(account_number=account_number)

    def run_command(self, **kw):
        cmd = CommandIO()
        call_command(
            'go_archive_transactions',
            stdout=cmd.stdout,
            stderr=cmd.stderr,
            **kw)
        return cmd

    def assert_remaining_transactions(self, transactions):
        self.assertEqual(
            set(Transaction.objects.all()), set(transactions))

    def mk_monthly_transactions(self, *from_times):
        transactions = []

        for from_time in from_times:
            from_date, to_date = this_month(from_time.date())
            transactions.extend([
                mk_transaction(self.account, created=from_date),
                mk_transaction(self.account, created=to_date)])

        return transactions

    def test_archive_transactions_without_deletion(self):
        self.s3_helper.patch_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket = Bucket('billing.archive')
        bucket.create()

        mk_statement(
            self.account,
            from_date=datetime(2014, 11, 1),
            to_date=datetime(2014, 11, 30))

        mk_statement(
            self.account,
            from_date=datetime(2014, 12, 1),
            to_date=datetime(2014, 12, 31))

        transactions = self.mk_monthly_transactions(
            datetime(2014, 11, 1),
            datetime(2014, 12, 1))

        cmd = self.run_command(
            email_address=self.user_email,
            months=['2014-11', '2014-12'])

        self.assertEqual(cmd.stderr.getvalue(), "")
        self.assertEqual(cmd.stdout.getvalue().splitlines(), [
            'Archiving transactions for account user@domain.com...',
            'Archiving transactions that occured in 2014-11...',
            'Archived to S3 as'
            ' transactions-test-0-user-2014-11-01-to-2014-11-30.json.',
            'Archive status is: transactions_uploaded.',
            '',
            'Archiving transactions that occured in 2014-12...',
            'Archived to S3 as'
            ' transactions-test-0-user-2014-12-01-to-2014-12-31.json.',
            'Archive status is: transactions_uploaded.',
            ''
        ])

        self.assert_remaining_transactions(transactions)

        [nov_archive] = TransactionArchive.objects.filter(
            account=self.account,
            from_date=datetime(2014, 11, 1),
            to_date=datetime(2014, 11, 30),
            status=TransactionArchive.STATUS_TRANSACTIONS_UPLOADED)

        [dec_archive] = TransactionArchive.objects.filter(
            account=self.account,
            from_date=datetime(2014, 12, 1),
            to_date=datetime(2014, 12, 31),
            status=TransactionArchive.STATUS_TRANSACTIONS_UPLOADED)

        s3_bucket = bucket.get_s3_bucket()
        [nov_s3_key, dec_s3_key] = sorted(
            list(s3_bucket.list()),
            key=lambda key: key.key)

        self.assertEqual(nov_s3_key.key, nov_archive.filename)
        self.assertEqual(dec_s3_key.key, dec_archive.filename)

    def test_archive_transactions_with_deletion(self):
        self.s3_helper.patch_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket = Bucket('billing.archive')
        bucket.create()

        mk_statement(
            self.account,
            from_date=datetime(2014, 11, 1),
            to_date=datetime(2014, 11, 30))

        mk_statement(
            self.account,
            from_date=datetime(2014, 12, 1),
            to_date=datetime(2014, 12, 31))

        self.mk_monthly_transactions(
            datetime(2014, 11, 1),
            datetime(2014, 12, 1))

        cmd = self.run_command(
            email_address=self.user_email,
            months=['2014-11', '2014-12'],
            delete=True)

        self.assertEqual(cmd.stderr.getvalue(), "")
        self.assertEqual(cmd.stdout.getvalue().splitlines(), [
            'Archiving transactions for account user@domain.com...',
            'Archiving transactions that occured in 2014-11...',
            'Archived to S3 as'
            ' transactions-test-0-user-2014-11-01-to-2014-11-30.json.',
            'Archive status is: archive_completed.',
            '',
            'Archiving transactions that occured in 2014-12...',
            'Archived to S3 as'
            ' transactions-test-0-user-2014-12-01-to-2014-12-31.json.',
            'Archive status is: archive_completed.',
            ''
        ])

        self.assert_remaining_transactions([])

        [nov_archive] = TransactionArchive.objects.filter(
            account=self.account,
            from_date=datetime(2014, 11, 1),
            to_date=datetime(2014, 11, 30),
            status=TransactionArchive.STATUS_ARCHIVE_COMPLETED)

        [dec_archive] = TransactionArchive.objects.filter(
            account=self.account,
            from_date=datetime(2014, 12, 1),
            to_date=datetime(2014, 12, 31),
            status=TransactionArchive.STATUS_ARCHIVE_COMPLETED)

        s3_bucket = bucket.get_s3_bucket()
        [nov_s3_key, dec_s3_key] = sorted(
            list(s3_bucket.list()),
            key=lambda key: key.key)

        self.assertEqual(nov_s3_key.key, nov_archive.filename)
        self.assertEqual(dec_s3_key.key, dec_archive.filename)

    def test_archive_transactions_missing_statements(self):
        self.s3_helper.patch_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket = Bucket('billing.archive')
        bucket.create()

        mk_statement(
            self.account,
            from_date=datetime(2014, 11, 1),
            to_date=datetime(2014, 11, 30))

        transactions = self.mk_monthly_transactions(
            datetime(2014, 10, 1),
            datetime(2014, 11, 1),
            datetime(2014, 12, 1))

        cmd = self.run_command(
            email_address=self.user_email,
            months=['2014-10', '2014-11', '2014-12'],
            delete=True)

        self.assertEqual(cmd.stderr.getvalue().splitlines(), [
            ('Aborting archiving, no statements found for the following'
             ' months:'),
            '2014-10',
            '2014-12'
        ])

        self.assert_remaining_transactions(transactions)
        self.assertEqual(list(bucket.get_s3_bucket().list()), [])

    def test_archive_transactions_no_statement_option(self):
        self.s3_helper.patch_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket = Bucket('billing.archive')
        bucket.create()

        mk_statement(
            self.account,
            from_date=datetime(2014, 12, 1),
            to_date=datetime(2014, 12, 31))

        self.mk_monthly_transactions(
            datetime(2014, 11, 1),
            datetime(2014, 12, 1))

        cmd = self.run_command(
            email_address=self.user_email,
            no_statement=True,
            months=['2014-11', '2014-12'])

        self.assertEqual(cmd.stderr.getvalue(), "")
        self.assertEqual(cmd.stdout.getvalue().splitlines(), [
            'Archiving transactions for account user@domain.com...',
            'Archiving transactions that occured in 2014-11...',
            'Archived to S3 as'
            ' transactions-test-0-user-2014-11-01-to-2014-11-30.json.',
            'Archive status is: transactions_uploaded.',
            '',
            'Archiving transactions that occured in 2014-12...',
            'Archived to S3 as'
            ' transactions-test-0-user-2014-12-01-to-2014-12-31.json.',
            'Archive status is: transactions_uploaded.',
            ''
        ])

        [nov_archive] = TransactionArchive.objects.filter(
            account=self.account,
            from_date=datetime(2014, 11, 1),
            to_date=datetime(2014, 11, 30))

        [dec_archive] = TransactionArchive.objects.filter(
            account=self.account,
            from_date=datetime(2014, 12, 1),
            to_date=datetime(2014, 12, 31))

        s3_bucket = bucket.get_s3_bucket()
        [nov_s3_key, dec_s3_key] = sorted(
            list(s3_bucket.list()),
            key=lambda key: key.key)

        self.assertEqual(nov_s3_key.key, nov_archive.filename)
        self.assertEqual(dec_s3_key.key, dec_archive.filename)
