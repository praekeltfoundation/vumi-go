from django.core.urlresolvers import reverse

from go.base.utils import get_router_view_definition
from go.base.tests.utils import VumiGoDjangoTestCase
from go.base import utils as base_utils


class DjangoGoRouterTestCase(VumiGoDjangoTestCase):
    use_riak = True

    TEST_ROUTER_NAME = u"Test Router"
    TEST_ROUTER_TYPE = u'keyword'

    def setUp(self):
        super(DjangoGoRouterTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def setup_router(self, config=None, started=True):
        if config is None:
            config = {}
        params = {
            'router_type': self.TEST_ROUTER_TYPE,
            'name': self.TEST_ROUTER_NAME,
            'description': u"Test router",
            'config': config,
        }
        if started:
            params['status'] = u'running'
        self.router = self.create_router(**params)
        self.router_key = self.router.key

    def get_latest_router(self):
        # We won't have too many here, so doing it naively is fine.
        routers = []
        for key in self.router_store.list_routers():
            routers.append(self.router_store.get_router_by_key(key))
        return max(routers, key=lambda r: r.created_at)

    def post_new_router(self, name='router name'):
        return self.client.post(self.get_new_view_url(), {
            'name': name,
            'router_type': self.TEST_ROUTER_TYPE,
        })

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()

    def get_view_url(self, view, router_key=None):
        if router_key is None:
            router_key = self.router_key
        view_def = get_router_view_definition(self.TEST_ROUTER_TYPE)
        return view_def.get_view_url(view, router_key=router_key)

    def get_new_view_url(self):
        return reverse('routers:new_router')

    def get_router(self, router_key=None):
        if router_key is None:
            router_key = self.router_key
        return self.user_api.get_router(router_key)
