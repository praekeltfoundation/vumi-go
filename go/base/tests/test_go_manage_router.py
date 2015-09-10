from pprint import pformat

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals(), dummy_classes=['GoAccountCommandTestCase']):
    from go.base.management.commands import go_manage_router
    from go.base.tests.helpers import GoAccountCommandTestCase


class TestGoManageRouter(GoAccountCommandTestCase):

    def setUp(self):
        self.setup_command(go_manage_router.Command)

    def test_list(self):
        router = self.user_helper.create_router(u'keyword')
        expected_output = "0. %s (type: %s, key: %s)\n" % (
            router.name, router.router_type, router.key)
        self.assert_command_output(expected_output, 'list')

    def test_show(self):
        router = self.user_helper.create_router(u'keyword')
        expected_output = "%s\n" % pformat(router.get_data())
        self.assert_command_output(
            expected_output, 'show', router_key=router.key)

    def test_show_config_no_router(self):
        self.assert_command_error(
            'Please specify a router key', 'show_config')
        self.assert_command_error(
            'Router does not exist',
            'show_config', router_key='foo')

    def test_show_config(self):
        router = self.user_helper.create_router(u'keyword', config={
            'http_api': {'api_tokens': ['token']},
        })
        expected_output = "{u'http_api': {u'api_tokens': [u'token']}}\n"
        self.assert_command_output(
            expected_output, 'show_config', router_key=router.key)

    def test_start_router(self):
        router = self.user_helper.create_router(u'keyword')
        self.assertEqual(router.archive_status, 'active')
        self.assertEqual(router.status, 'stopped')

        self.assert_command_output(
            'Starting router...\nRouter started\n',
            'start', router_key=router.key)

        router = self.user_helper.get_router(router.key)
        self.assertEqual(router.status, 'starting')
        [start_command] = self.vumi_helper.amqp_connection.get_commands()
        self.assertEqual(start_command['command'], 'start')

    def test_stop_router(self):
        router = self.user_helper.create_router(u'keyword', started=True)
        self.assertEqual(router.archive_status, 'active')
        self.assertEqual(router.status, 'running')

        self.assert_command_output(
            'Stopping router...\nRouter stopped\n',
            'stop', router_key=router.key)

        router = self.user_helper.get_router(router.key)
        self.assertEqual(router.status, 'stopping')
        [stop_command] = self.vumi_helper.amqp_connection.get_commands()
        self.assertEqual(stop_command['command'], 'stop')

    def test_archive_router(self):
        router = self.user_helper.create_router(u'keyword')
        self.assertEqual(router.archive_status, 'active')
        self.assertEqual(router.status, 'stopped')

        self.assert_command_output(
            'Archiving router...\nRouter archived\n',
            'archive', router_key=router.key)

        router = self.user_helper.get_router(router.key)
        self.assertEqual(router.archive_status, 'archived')
