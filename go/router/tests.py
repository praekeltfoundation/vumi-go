import urllib

from django.core.urlresolvers import reverse

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.utils import get_router_view_definition
from go.vumitools.router.models import ROUTER_ARCHIVED


class RouterViewsTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(RouterViewsTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def get_view_url(self, view, router_key):
        view_def = get_router_view_definition('keyword', None)
        return view_def.get_view_url(view, router_key=router_key)

    def mk_router(self, **kw):
        params = {
            'router_type': u'keyword',
            'name': u'kwr',
            'description': u'keyword router',
            'config': {},
        }
        params.update(kw)
        return self.user_api.new_router(**params)

    def test_index(self):
        router = self.mk_router()
        archived_router = self.mk_router(
            name=u'archived', archive_status=ROUTER_ARCHIVED)
        response = self.client.get(reverse('routers:index'))
        self.assertContains(response, urllib.quote(router.key))
        self.assertNotContains(response, urllib.quote(archived_router.key))

    def test_get_new_router(self):
        response = self.client.get(reverse('routers:new_router'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Router name')
        self.assertContains(response, 'kind of router')
        self.assertContains(response, 'keyword')
        self.assertNotContains(response, 'bulk_message')

    def test_post_new_router(self):
        router_data = {
            'name': 'new router',
            'router_type': 'keyword',
        }
        response = self.client.post(reverse('routers:new_router'), router_data)
        [router] = self.user_api.active_routers()
        self.assertRedirects(response, self.get_view_url('edit', router.key))
        self.assertEqual(router.name, 'new router')
        self.assertEqual(router.router_type, 'keyword')

    def test_show_router_missing(self):
        response = self.client.get(self.get_view_url('show', u'missingrouter'))
        self.assertEqual(response.status_code, 404)

    def test_show_router(self):
        router = self.mk_router()
        response = self.client.get(self.get_view_url('show', router.key))
        self.assertContains(response, router.name)
        self.assertContains(response, router.description)

    def test_archive_router(self):
        router = self.mk_router()
        self.assertFalse(router.archived())
        response = self.client.post(self.get_view_url('archive', router.key))
        self.assertRedirects(response, reverse('routers:index'))
        router = self.user_api.get_router(router.key)
        self.assertTrue(router.archived())
