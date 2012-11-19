# -*- coding: utf-8 -*-
from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_list_accounts
from StringIO import StringIO


class GoListAccountsCommandTestCase(VumiGoDjangoTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoListAccountsCommandTestCase, self).setUp()
        self.setup_api()
        self.user = self.mk_django_user()

        self.command = go_list_accounts.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_account_listing(self):
        self.command.handle()
        self.assertEqual(self.command.stdout.getvalue(),
            '0. Test User <username> [%s]\n' % (
                self.user.get_profile().user_account))

    def test_unicode_account_listing(self):
        self.user.first_name = u"Tëßt"
        self.user.save()
        self.command.handle()
        profile = self.user.get_profile()
        self.assertEqual(self.command.stdout.getvalue(),
            '0. T\xc3\xab\xc3\x9ft User <username> [%s]\n' % (
                str(profile.user_account)))

    def test_account_matching(self):
        self.command.handle('user')
        self.assertEqual(self.command.stdout.getvalue(),
            '0. Test User <username> [%s]\n' % (
                self.user.get_profile().user_account))

    def test_account_mismatching(self):
        self.command.handle('foo')
        self.assertEqual(self.command.stderr.getvalue(),
            'No accounts found.\n')
        self.assertEqual(self.command.stdout.getvalue(), '')
