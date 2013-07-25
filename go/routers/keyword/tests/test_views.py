from go.routers.tests.base import DjangoGoRouterTestCase


class KeywordViewTests(DjangoGoRouterTestCase):
    TEST_ROUTER_TYPE = u'keyword'

    def test_new_router(self):
        self.assertEqual(len(self.router_store.list_routers()), 0)
        response = self.post_new_router()
        self.assertEqual(len(self.router_store.list_routers()), 1)
        router = self.get_latest_router()
        self.assertRedirects(response, self.get_view_url('edit', router.key))

    def test_show(self):
        """
        Test showing the router
        """
        self.setup_router()
        response = self.client.get(self.get_view_url('show'))
        router = response.context[0].get('router')
        self.assertEqual(router.name, self.TEST_ROUTER_NAME)

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
            'keyword_endpoint_mapping-0-keyword_regex': ['foo'],
            'keyword_endpoint_mapping-0-target_endpoint': ['bar'],
            'keyword_endpoint_mapping-0-DELETE': [''],
            'keyword_endpoint_mapping-1-keyword_regex': ['baz'],
            'keyword_endpoint_mapping-1-target_endpoint': ['quux'],
            'keyword_endpoint_mapping-1-DELETE': [''],
        })
        self.assertRedirects(response, self.get_view_url('show'))
        router = self.get_router()
        self.assertEqual(router.config, {u'keyword_endpoint_mapping': {
            'foo': 'bar',
            'baz': 'quux',
        }})
