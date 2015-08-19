import urllib

from go.vumitools.router.models import ROUTER_ARCHIVED
from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.urlresolvers import reverse

    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.base.utils import get_router_view_definition


class TestRouterViews(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def get_view_url(self, view, router_key):
        view_def = get_router_view_definition('keyword', None)
        return view_def.get_view_url(view, router_key=router_key)

    def test_index(self):
        router = self.user_helper.create_router(u'keyword')
        archived_router = self.user_helper.create_router(
            u'keyword', name=u'archived', archive_status=ROUTER_ARCHIVED)
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
        [router] = self.user_helper.user_api.active_routers()
        self.assertRedirects(response, self.get_view_url('edit', router.key))
        self.assertEqual(router.name, 'new router')
        self.assertEqual(router.router_type, 'keyword')

    def test_show_router_missing(self):
        response = self.client.get(self.get_view_url('show', u'missingrouter'))
        self.assertEqual(response.status_code, 404)

    def test_show_router(self):
        router = self.user_helper.create_router(u'keyword')
        response = self.client.get(self.get_view_url('show', router.key))
        self.assertContains(response, router.name)
        self.assertContains(response, router.description)

    def test_archive_router(self):
        router = self.user_helper.create_router(u'keyword')
        self.assertFalse(router.archived())
        response = self.client.post(self.get_view_url('archive', router.key))
        self.assertRedirects(response, reverse('routers:index'))
        router = self.user_helper.user_api.get_router(router.key)
        self.assertTrue(router.archived())
