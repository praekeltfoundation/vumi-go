from StringIO import StringIO

from django.core.management.base import CommandError

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_assign_tagpool


class GoAssignTagpoolCommandTestCase(VumiGoDjangoTestCase):

    use_riak = True

    def setUp(self):
        super(GoAssignTagpoolCommandTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.command = go_assign_tagpool.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()
        self.declare_tags("pool", num_tags=2)

    def handle_command(self, email_address=None, tagpool=None,
                       max_keys=None, update=False):
        if email_address is None:
            email_address = self.django_user.email
        self.command.handle(**{
            "email-address": email_address,
            "tagpool": tagpool,
            "max-keys": max_keys,
            "update": update
        })
        output = self.command.stdout.getvalue().strip().split('\n')
        return output

    def assert_permissions(self, **perms):
        account = self.user_api.get_user_account()
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
        self.add_tagpool_permission(u"pool", max_keys=1)
        self.assertRaisesRegexp(
            CommandError,
            "Permission already exists, use --update to update the value of"
            " max-keys",
            self.handle_command, tagpool="pool", max_keys=0)
        self.assert_permissions(pool=1)

    def test_update_permission(self):
        self.add_tagpool_permission(u"pool", max_keys=1)
        output = self.handle_command(tagpool="pool", max_keys=2, update=True)
        self.assertEqual(output, [''])
        self.assert_permissions(pool=2)

    def test_fails_on_bad_tagpool_name(self):
        self.assertRaisesRegexp(
            CommandError, "Tagpool 'unknown' does not exist",
            self.handle_command, tagpool="unknown", max_keys=0)
        self.assert_permissions()
