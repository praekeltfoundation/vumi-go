from go.vumitools.api import VumiApiCommand
from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase
    from go.routers.tests.view_helpers import RouterViewsHelper


class ApplicationMultiplexerViewTests(GoDjangoTestCase):

    def setUp(self):
        self.router_helper = self.add_helper(
            RouterViewsHelper(u'app_multiplexer')
        )
        self.user_helper = self.router_helper.vumi_helper.get_or_create_user()
        self.client = self.router_helper.get_client()

    def test_new_router(self):
        router_store = self.user_helper.user_api.router_store
        self.assertEqual([], router_store.list_routers())

        response = self.client.post(self.router_helper.get_new_view_url(), {
            'name': u"myrouter",
            'router_type': u'app_multiplexer',
        })
        [router_key] = router_store.list_routers()
        rtr_helper = self.router_helper.get_router_helper_by_key(router_key)
        self.assertRedirects(response, rtr_helper.get_view_url('edit'))

    def test_show_stopped(self):
        rtr_helper = self.router_helper.create_router_helper(name=u"myrouter")
        response = self.client.get(rtr_helper.get_view_url('show'))
        router = response.context[0].get('router')
        self.assertEqual(router.name, u"myrouter")
        self.assertContains(response, rtr_helper.get_view_url('start'))
        self.assertContains(
            response,
            '<button class="btn action" data-action="stop" ' +
            ' data-url="%s" disabled>Deactivate</button>'
            % rtr_helper.get_view_url('stop'), html=True)

    def test_show_running(self):
        rtr_helper = self.router_helper.create_router_helper(
            name=u"myrouter", started=True)
        response = self.client.get(rtr_helper.get_view_url('show'))
        router = response.context[0].get('router')
        self.assertEqual(router.name, u"myrouter")
        self.assertContains(
            response,
            '<button class="btn action" data-action="activate" ' +
            'data-url="%s" disabled>Activate</button>'
            % rtr_helper.get_view_url('start'), html=True)
        self.assertContains(response, rtr_helper.get_view_url('stop'))

    def test_start(self):
        rtr_helper = self.router_helper.create_router_helper(started=False)

        response = self.client.post(rtr_helper.get_view_url('start'))
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertTrue(router.starting())
        [start_cmd] = self.router_helper.get_api_commands_sent()
        self.assertEqual(
            start_cmd, VumiApiCommand.command(
                '%s_router' % (router.router_type,), 'start',
                command_id=start_cmd["command_id"],
                user_account_key=router.user_account.key,
                router_key=router.key))

    def test_stop(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)

        response = self.client.post(rtr_helper.get_view_url('stop'))
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertTrue(router.stopping())
        [stop_cmd] = self.router_helper.get_api_commands_sent()
        self.assertEqual(
            stop_cmd, VumiApiCommand.command(
                '%s_router' % (router.router_type,), 'stop',
                command_id=stop_cmd["command_id"],
                user_account_key=router.user_account.key,
                router_key=router.key))

    def test_initial_config(self):
        rtr_helper = self.router_helper.create_router_helper(
            started=True, config={
                'menu_title': {'content': 'Please select an application'},
                'entries': [
                    {
                        'label': 'Flappy Bird',
                        'endpoint': 'flappy-bird',
                    },
                ]})
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please select an application')
        self.assertContains(response, 'Flappy Bird')
        self.assertContains(response, 'flappy-bird')

    def test_initial_config_empty(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_user_input_good(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'menu_title-content': ['Please select an application'],
            'entries-TOTAL_FORMS': ['2'],
            'entries-INITIAL_FORMS': ['0'],
            'entries-MAX_NUM_FORMS': [''],
            'entries-0-application_label': ['Flappy Bird'],
            'entries-0-endpoint_name': ['flappy-bird'],
            'entries-0-DELETE': [''],
            'entries-0-ORDER': ['0'],
            'entries-1-application_label': ['Mama'],
            'entries-1-endpoint_name': ['mama'],
            'entries-1-DELETE': [''],
            'entries-1-ORDER': ['1'],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {
            u'menu_title': {u'content': u'Please select an application'},
            u'entries': [
                {
                    u'label': u'Flappy Bird',
                    u'endpoint': u'flappy-bird',
                },
                {
                    u'label': u'Mama',
                    u'endpoint': u'mama',
                }]})

    def test_user_input_good_with_delete(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'menu_title-content': ['Please select an application'],
            'entries-TOTAL_FORMS': ['2'],
            'entries-INITIAL_FORMS': ['0'],
            'entries-MAX_NUM_FORMS': [''],
            'entries-0-application_label': ['Flappy Bird'],
            'entries-0-endpoint_name': ['flappy-bird'],
            'entries-0-DELETE': ['on'],
            'entries-0-ORDER': ['0'],
            'entries-1-application_label': ['Mama'],
            'entries-1-endpoint_name': ['mama'],
            'entries-1-DELETE': [''],
            'entries-1-ORDER': ['1'],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {
            u'menu_title': {u'content': u'Please select an application'},
            u'entries': [
                {
                    u'label': u'Mama',
                    u'endpoint': u'mama',
                }]})
