# -*- coding: utf-8 -*-
from StringIO import StringIO

from go.base.management.commands import go_list_accounts
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoListAccountsCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.contact_store = self.user_helper.user_api.contact_store

        self.command = go_list_accounts.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_account_listing(self):
        self.command.handle()
        self.assertEqual(self.command.stdout.getvalue(),
            '0. Test User <user@domain.com> [%s]\n' % (
                self.user_helper.account_key,))

    def test_unicode_account_listing(self):
        django_user = self.user_helper.get_django_user()
        django_user.first_name = u"Tëßt"
        django_user.save()
        self.command.handle()
        self.assertEqual(self.command.stdout.getvalue(),
            '0. T\xc3\xab\xc3\x9ft User <user@domain.com> [%s]\n' % (
                str(self.user_helper.account_key,)))

    def test_account_matching(self):
        self.command.handle('user')
        self.assertEqual(self.command.stdout.getvalue(),
            '0. Test User <user@domain.com> [%s]\n' % (
                self.user_helper.account_key,))

    def test_account_mismatching(self):
        self.command.handle('foo')
        self.assertEqual(self.command.stderr.getvalue(),
            'No accounts found.\n')
        self.assertEqual(self.command.stdout.getvalue(), '')
