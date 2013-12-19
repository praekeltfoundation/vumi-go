from StringIO import StringIO

from django.core.management.base import CommandError

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.base.management.commands import go_assign_tagpool


class TestGoAssignTagpoolCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

        self.command = go_assign_tagpool.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()
        self.vumi_helper.setup_tagpool(u"pool", [u"tag1", u"tag2"])

    def handle_command(self, tagpool=None, max_keys=None, update=False):
        self.command.handle(**{
            "email-address": self.user_helper.get_django_user().email,
            "tagpool": tagpool,
            "max-keys": max_keys,
            "update": update
        })
        output = self.command.stdout.getvalue().strip().split('\n')
        return output

    def assert_permissions(self, **perms):
        account = self.user_helper.get_user_account()
        for permissions in account.tagpools.load_all_bunches():
            for p in permissions:
                if p.tagpool in perms:
                    self.assertEqual((p.tagpool, p.max_keys),
                                     (p.tagpool, perms.pop(p.tagpool)))
                else:
                    self.fail("Unexpected tagpool permission %r" % (p,))
        self.assertEqual(perms, {})

    def test_create_permission(self):
        output = self.handle_command(tagpool="pool", max_keys=1)
        self.assertEqual(output, [''])
        self.assert_permissions(pool=1)

    def test_create_permission_no_max(self):
        output = self.handle_command(tagpool="pool", max_keys=0)
        self.assertEqual(output, [''])
        self.assert_permissions(pool=None)

    def test_create_fails_on_existing_permission(self):
        self.user_helper.add_tagpool_permission(u"pool", max_keys=1)
        self.assertRaisesRegexp(
            CommandError,
            "Permission already exists, use --update to update the value of"
            " max-keys",
            self.handle_command, tagpool="pool", max_keys=0)
        self.assert_permissions(pool=1)

    def test_update_permission(self):
        self.user_helper.add_tagpool_permission(u"pool", max_keys=1)
        output = self.handle_command(tagpool="pool", max_keys=2, update=True)
        self.assertEqual(output, [''])
        self.assert_permissions(pool=2)

    def test_fails_on_bad_tagpool_name(self):
        self.assertRaisesRegexp(
            CommandError, "Tagpool 'unknown' does not exist",
            self.handle_command, tagpool="unknown", max_keys=0)
        self.assert_permissions()
