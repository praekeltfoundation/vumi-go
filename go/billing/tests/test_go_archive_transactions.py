# -*- coding: utf-8 -*-

from datetime import datetime

import moto

from django.core.management import call_command

from go.base.tests.helpers import (
    GoDjangoTestCase, DjangoVumiApiHelper, CommandIO)
from go.billing.models import Account, Transaction, TransactionArchive
from go.billing.tests.helpers import mk_transaction, this_month


class TestArchiveTransactions(GoDjangoTestCase):
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
            'go_archive_transactions',
            stdout=cmd.stdout,
            stderr=cmd.stderr,
            **kw)
        return cmd

    def assert_remaining_transactions(self, transactions):
        self.assertEqual(
            set(Transaction.objects.all()), set(transactions))

    @moto.mock_s3
    def test_archive_transactions_without_deletion(self):
        bucket = self.vumi_helper.patch_s3_bucket_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket.create()

        from_time = datetime(2014, 12, 1)
        from_date, to_date = this_month(from_time.date())
        transaction_1 = mk_transaction(self.account, created=from_date)
        transaction_2 = mk_transaction(self.account, created=to_date)

        cmd = self.run_command(
            email_address=self.user_email,
            from_date='2014-12-01',
            to_date='2014-12-31')

        self.assertEqual(cmd.stderr.getvalue(), "")
        self.assertEqual(cmd.stdout.getvalue().splitlines(), [
            'Transactions archived for account user@domain.com.',
            'Archived to S3 as'
            ' transactions-test-0-user-2014-12-01-to-2014-12-31.json.',
            'Archive status is: transactions_uploaded.'
        ])

        self.assert_remaining_transactions([transaction_1, transaction_2])

        archive = TransactionArchive.objects.get(account=self.account)
        self.assertEqual(
            archive.status, TransactionArchive.STATUS_TRANSACTIONS_UPLOADED)
        self.assertEqual(archive.from_date, from_date)
        self.assertEqual(archive.to_date, to_date)

        s3_bucket = bucket.get_s3_bucket()
        [s3_key] = list(s3_bucket.list())
        self.assertEqual(s3_key.key, archive.filename)

    @moto.mock_s3
    def test_archive_transactions_with_deletion(self):
        bucket = self.vumi_helper.patch_s3_bucket_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket.create()

        from_time = datetime(2014, 12, 1)
        from_date, to_date = this_month(from_time.date())
        mk_transaction(self.account, created=from_date)
        mk_transaction(self.account, created=to_date)

        cmd = self.run_command(
            email_address=self.user_email,
            from_date='2014-12-01',
            to_date='2014-12-31',
            delete=True)

        self.assertEqual(cmd.stderr.getvalue(), "")
        self.assertEqual(cmd.stdout.getvalue().splitlines(), [
            'Transactions archived for account user@domain.com.',
            'Archived to S3 as'
            ' transactions-test-0-user-2014-12-01-to-2014-12-31.json.',
            'Archive status is: archive_completed.'
        ])

        self.assert_remaining_transactions([])

        archive = TransactionArchive.objects.get(account=self.account)
        self.assertEqual(
            archive.status, TransactionArchive.STATUS_ARCHIVE_COMPLETED)
        self.assertEqual(archive.from_date, from_date)
        self.assertEqual(archive.to_date, to_date)

        s3_bucket = bucket.get_s3_bucket()
        [s3_key] = list(s3_bucket.list())
        self.assertEqual(s3_key.key, archive.filename)
