import urllib

from django.test.client import Client
from django.core.urlresolvers import reverse

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base import utils as base_utils
from go.base.utils import get_router_view_definition


class RouterViewsTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(RouterViewsTestCase, self).setUp()
        self.setup_api()
        self.user = self.mk_django_user()
        self.user_api = base_utils.vumi_api_for_user(self.user)

        self.client = Client()
        self.client.login(username=self.user.username, password='password')

    def get_view_url(self, view, router_key):
        view_def = get_router_view_definition('keyword', None)
        return view_def.get_view_url(view, router_key=router_key)

    def test_index(self):
        router = self.user_api.new_router(
            router_type=u'keyword', name=u'kwr', description=u'keyword router',
            config={})
        response = self.client.get(reverse('routers:index'))
        self.assertContains(response, urllib.quote(router.key))

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
        show_url = reverse('routers:router', kwargs={
            'router_key': router.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        self.assertEqual(router.name, 'new router')
        self.assertEqual(router.router_type, 'keyword')

    def test_show_router_missing(self):
        response = self.client.get(self.get_view_url('show', u'missingrouter'))
        self.assertEqual(response.status_code, 404)

    def test_show_router(self):
        router = self.user_api.new_router(
            router_type=u'keyword', name=u'kwr', description=u'keyword router',
            config={})
        response = self.client.get(self.get_view_url('show', router.key))
        self.assertContains(response, router.name)
        self.assertContains(response, router.description)
