from go.base.tests.helpers import GoDjangoTestCase
from go.routers.tests.view_helpers import RouterViewsHelper


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
