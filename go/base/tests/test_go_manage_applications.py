from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.management.base import CommandError

    from go.base.management.commands import go_manage_application
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoManageApplicationCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

        self.command = go_manage_application.Command()
        self.vumi_helper.patch_config(VUMI_INSTALLED_APPS={
            'go.apps.dummy': {
                'namespace': 'dummy',
                'display_name': 'dummy'
            }
        })

    def get_riak_account(self):
        return self.profile.get_user_account()

    def set_permissions(self, application, enabled):
        self.command.handle(**{
            'email_address': self.user_helper.get_django_user().email,
            'application_module': application,
            'enable': enabled,
            'disable': not enabled,
        })

    def assert_permission(self, app, enabled):
        self.assertEqual(
            enabled, (app in self.user_helper.user_api.applications()))

    def test_enable_permissions(self):
        self.assert_permission('go.apps.dummy', enabled=False)
        self.set_permissions('go.apps.dummy', enabled=True)
        self.assert_permission('go.apps.dummy', enabled=True)

    def test_double_permission_error(self):
        self.set_permissions('go.apps.dummy', enabled=True)
        self.assertRaises(
            CommandError, self.set_permissions, 'go.apps.dummy', enabled=True)

    def test_disable_permissions(self):
        self.set_permissions('go.apps.dummy', enabled=True)
        self.assert_permission('go.apps.dummy', enabled=True)
        self.set_permissions('go.apps.dummy', enabled=False)
        self.assert_permission('go.apps.dummy', enabled=False)

    def test_disable_permissions_for_non_enabled_app(self):
        self.assertRaises(
            CommandError, self.set_permissions, 'go.apps.dummy', enabled=False)
