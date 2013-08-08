from go.routers.tests.base import DjangoGoRouterTestCase
from go.vumitools.tests.utils import VumiApiCommand


class KeywordViewTests(DjangoGoRouterTestCase):
    TEST_ROUTER_TYPE = u'keyword'

    def test_new_router(self):
        self.assertEqual(len(self.router_store.list_routers()), 0)
        response = self.post_new_router()
        self.assertEqual(len(self.router_store.list_routers()), 1)
        router = self.get_latest_router()
        self.assertRedirects(response, self.get_view_url('edit', router.key))

    def test_show_stopped(self):
        self.setup_router(started=False)
        response = self.client.get(self.get_view_url('show'))
        router = response.context[0].get('router')
        self.assertEqual(router.name, self.TEST_ROUTER_NAME)
        self.assertContains(response, self.get_view_url('start'))
        self.assertNotContains(response, self.get_view_url('stop'))

    def test_show_running(self):
        self.setup_router()
        response = self.client.get(self.get_view_url('show'))
        router = response.context[0].get('router')
        self.assertEqual(router.name, self.TEST_ROUTER_NAME)
        self.assertNotContains(response, self.get_view_url('start'))
        self.assertContains(response, self.get_view_url('stop'))

    def test_start(self):
        self.setup_router(started=False)

        response = self.client.post(self.get_view_url('start'))
        self.assertRedirects(response, self.get_view_url('show'))
        router = self.get_router()
        self.assertTrue(router.starting())
        [start_cmd] = self.get_api_commands_sent()
        self.assertEqual(
            start_cmd, VumiApiCommand.command(
                '%s_router' % (router.router_type,), 'start',
                user_account_key=router.user_account.key,
                router_key=router.key))

    def test_stop(self):
        self.setup_router(started=True)

        response = self.client.post(self.get_view_url('stop'))
        self.assertRedirects(response, self.get_view_url('show'))
        router = self.get_router()
        self.assertTrue(router.stopping())
        [start_cmd] = self.get_api_commands_sent()
        self.assertEqual(
            start_cmd, VumiApiCommand.command(
                '%s_router' % (router.router_type,), 'stop',
                user_account_key=router.user_account.key,
                router_key=router.key))

    def test_get_edit_empty_config(self):
        self.setup_router()
        response = self.client.get(self.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_get_edit_small_config(self):
        self.setup_router({'keyword_endpoint_mapping': {
            'mykeyw[o0]rd': 'target_endpoint',
        }})
        response = self.client.get(self.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mykeyw[o0]rd')
        self.assertContains(response, 'target_endpoint')

    def test_edit_router_keyword_config(self):
        self.setup_router()
        router = self.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(self.get_view_url('edit'), {
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
        self.assertRedirects(response, self.get_view_url('show'))
        router = self.get_router()
        self.assertEqual(router.config, {u'keyword_endpoint_mapping': {
            'foo': 'bar',
            'baz': 'quux',
        }})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['bar', 'quux']))
