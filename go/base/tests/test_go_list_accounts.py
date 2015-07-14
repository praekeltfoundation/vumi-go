# -*- coding: utf-8 -*-
from StringIO import StringIO

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
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

    def test_show_pools(self):
        self.vumi_helper.setup_tagpool(u"pool-1", [])
        self.user_helper.add_tagpool_permission(u"pool-1")

        self.command.handle(**{'show-pools': True})
        self.assertEqual(self.command.stdout.getvalue().splitlines(), [
            "0. Test User <user@domain.com> [test-0-user]",
            "  Pools:",
            "    u'pool-1' (max-keys: None)",
        ])

    def test_show_tags(self):
        self.vumi_helper.setup_tagpool(u"pool-1", [u"tag-1"])
        self.user_helper.add_tagpool_permission(u"pool-1")
        self.user_helper.user_api.acquire_specific_tag((u"pool-1", u"tag-1"))

        self.command.handle(**{'show-tags': True})
        self.assertEqual(self.command.stdout.getvalue().splitlines(), [
            "0. Test User <user@domain.com> [test-0-user]",
            "  Tags:",
            "    (u'pool-1', u'tag-1')",
        ])
