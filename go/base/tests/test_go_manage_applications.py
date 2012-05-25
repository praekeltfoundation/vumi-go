from django.contrib.auth.models import User
from django.core.management.base import CommandError
from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_manage_application


class GoManageApplicationCommandTestCase(VumiGoDjangoTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoManageApplicationCommandTestCase, self).setUp()
        self.user = User.objects.create(username='test@user.com',
            password='password', email='test@user.com')
        self.profile = self.user.get_profile()

    def get_riak_account(self):
        return self.profile.get_user_account()

    def set_permissions(self, user, enabled, application):
        command = go_manage_application.Command()
        command.handle_validated(**{
            'email-address': user.username,
            'application-module': application,
            'enable': enabled,
            'disable': not enabled,
        })

    def test_enable_permissions(self):
        self.set_permissions(self.user, enabled=True,
            application='go.apps.test')
        riak_account = self.get_riak_account()
        permissions = riak_account.applications.get_all()
        apps = [p.application for p in permissions]
        self.assertTrue('go.apps.test' in apps)

    def test_double_permission_error(self):
        self.set_permissions(self.user, enabled=True,
            application='go.apps.tests')
        self.assertRaises(CommandError, self.set_permissions,
            self.user, enabled=True, application='go.apps.tests')

    def test_disable_permissions(self):
        self.set_permissions(self.user, enabled=True,
            application='go.apps.test')
        self.set_permissions(self.user, enabled=False,
            application='go.apps.test')
        riak_account = self.get_riak_account()
        permissions = riak_account.applications.get_all()
        apps = [p.application for p in permissions]
        self.assertFalse('go.apps.test' in apps)

    def test_disable_permissions_for_non_enabled_app(self):
        self.assertRaises(CommandError, self.set_permissions,
            self.user, enabled=False, application='go.apps.tests')
