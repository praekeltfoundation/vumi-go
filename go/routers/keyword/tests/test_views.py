from go.base.tests.helpers import GoDjangoTestCase
from go.routers.tests.view_helpers import RouterViewsHelper
from go.vumitools.api import VumiApiCommand


class KeywordViewTests(GoDjangoTestCase):

    def setUp(self):
        self.router_helper = self.add_helper(RouterViewsHelper(u'keyword'))
        self.user_helper = self.router_helper.vumi_helper.get_or_create_user()
        self.client = self.router_helper.get_client()

    def test_new_router(self):
        router_store = self.user_helper.user_api.router_store
        self.assertEqual([], router_store.list_routers())

        response = self.client.post(self.router_helper.get_new_view_url(), {
            'name': u"myrouter",
            'router_type': u'keyword',
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

    def test_get_edit_empty_config(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_get_edit_small_config(self):
        rtr_helper = self.router_helper.create_router_helper(
            started=True, config={
                'keyword_endpoint_mapping': {
                    'mykeyw[o0]rd': 'target_endpoint',
                },
            })
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mykeyw[o0]rd')
        self.assertContains(response, 'target_endpoint')

    def test_edit_router_keyword_config(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'keyword_endpoint_mapping-TOTAL_FORMS': ['2'],
            'keyword_endpoint_mapping-INITIAL_FORMS': ['0'],
            'keyword_endpoint_mapping-MAX_NUM_FORMS': [''],
            'keyword_endpoint_mapping-0-keyword': ['foo'],
            'keyword_endpoint_mapping-0-target_endpoint': ['bar'],
            'keyword_endpoint_mapping-0-DELETE': [''],
            'keyword_endpoint_mapping-1-keyword': ['baz'],
            'keyword_endpoint_mapping-1-target_endpoint': ['quux'],
            'keyword_endpoint_mapping-1-DELETE': [''],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'keyword_endpoint_mapping': {
            'foo': 'bar',
            'baz': 'quux',
        }})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['bar', 'quux']))

    def test_edit_router_keyword_config_with_delete(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'keyword_endpoint_mapping-TOTAL_FORMS': ['2'],
            'keyword_endpoint_mapping-INITIAL_FORMS': ['0'],
            'keyword_endpoint_mapping-MAX_NUM_FORMS': [''],
            'keyword_endpoint_mapping-0-keyword': ['foo'],
            'keyword_endpoint_mapping-0-target_endpoint': ['bar'],
            'keyword_endpoint_mapping-0-DELETE': ['on'],
            'keyword_endpoint_mapping-1-keyword': ['baz'],
            'keyword_endpoint_mapping-1-target_endpoint': ['quux'],
            'keyword_endpoint_mapping-1-DELETE': [''],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'keyword_endpoint_mapping': {
            'baz': 'quux',
        }})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['quux']))
