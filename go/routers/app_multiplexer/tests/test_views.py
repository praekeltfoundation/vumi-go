from go.base.tests.helpers import GoDjangoTestCase
from go.routers.tests.view_helpers import RouterViewsHelper
from go.vumitools.api import VumiApiCommand


class ApplicationMultiplexerViewTests(GoDjangoTestCase):

    def setUp(self):
        self.router_helper = self.add_helper(
            RouterViewsHelper(u'application_multiplexer')
        )
        self.user_helper = self.router_helper.vumi_helper.get_or_create_user()
        self.client = self.router_helper.get_client()

    def test_new_router(self):
        router_store = self.user_helper.user_api.router_store
        self.assertEqual([], router_store.list_routers())

        response = self.client.post(self.router_helper.get_new_view_url(), {
            'name': u"myrouter",
            'router_type': u'application_multiplexer',
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
        self.assertNotContains(response, rtr_helper.get_view_url('stop'))

    def test_show_running(self):
        rtr_helper = self.router_helper.create_router_helper(
            name=u"myrouter", started=True)
        response = self.client.get(rtr_helper.get_view_url('show'))
        router = response.context[0].get('router')
        self.assertEqual(router.name, u"myrouter")
        self.assertNotContains(response, rtr_helper.get_view_url('start'))
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
                user_account_key=router.user_account.key,
                router_key=router.key))

    def test_stop(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)

        response = self.client.post(rtr_helper.get_view_url('stop'))
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertTrue(router.stopping())
        [start_cmd] = self.router_helper.get_api_commands_sent()
        self.assertEqual(
            start_cmd, VumiApiCommand.command(
                '%s_router' % (router.router_type,), 'stop',
                user_account_key=router.user_account.key,
                router_key=router.key))

    def test_get_edit_empty_config(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_get_edit_small_config(self):
        rtr_helper = self.router_helper.create_router_helper(
            started=True, config={
                'endpoints': {
                    'mykeyw[o0]rd': 'target_endpoint',
                },
            })
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mykeyw[o0]rd')
        self.assertContains(response, 'target_endpoint')

    def test_config_validate_unique_endpoints(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'menu_title-menu_title': ['foo'],

            'endpoints-TOTAL_FORMS': ['2'],
            'endpoints-INITIAL_FORMS': ['0'],
            'endpoints-MAX_NUM_FORMS': [''],
            'endpoints-0-application_title': ['foo'],
            'endpoints-0-target_endpoint': ['cat'],
            'endpoints-0-DELETE': [''],
            'endpoints-1-application_title': ['foo'],
            'endpoints-1-target_endpoint': ['dog'],
            'endpoints-1-DELETE': [''],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ('Application titles and endpoints '
                                       'should be distinct.'))

    def test_config_validate_menu_length(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})

        fields = {
            'menu_title-menu_title': ['Please select:'],
            'endpoints-TOTAL_FORMS': ['60'],
            'endpoints-INITIAL_FORMS': ['0'],
            'endpoints-MAX_NUM_FORMS': [''],
        }
        for i in range(0, 60):
            fields.update({
                'endpoints-%s-application_title' % i: ['foo-%s' % i],
                'endpoints-%s-target_endpoint' % i: ['bar-%s' % i],
                'endpoints-%s-DELETE' % i: [''],
            })
        response = self.client.post(rtr_helper.get_view_url('edit'), fields)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response,
                            ("The generated menu is too large. Either reduce "
                             "the length of application titles or the number "
                             "of applications."))
