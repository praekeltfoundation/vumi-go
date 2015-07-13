from django.core.urlresolvers import reverse

from zope.interface import implements

from vumi.tests.helpers import generate_proxies, IHelper

from go.base import utils as base_utils
from go.base.tests.helpers import DjangoVumiApiHelper
from .helpers import RouterHelper


class RouterViewsHelper(object):
    implements(IHelper)

    def __init__(self, router_type):
        self.router_type = router_type

        self.vumi_helper = DjangoVumiApiHelper()
        self._router_helper = RouterHelper(
            router_type, self.vumi_helper)

        # Proxy methods from our helpers.
        generate_proxies(self, self._router_helper)
        generate_proxies(self, self.vumi_helper)

    def setup(self):
        self.vumi_helper.setup()
        self.vumi_helper.make_django_user()

    def cleanup(self):
        return self.vumi_helper.cleanup()

    def get_new_view_url(self):
        return reverse('routers:new_router')

    def get_router_helper(self, router):
        return self.get_router_helper_by_key(router.key)

    def create_router_helper(self, *args, **kw):
        router = self.create_router(*args, **kw)
        return self.get_router_helper(router)

    def get_router_helper_by_key(self, router_key):
        return RouterViewHelper(self, router_key)

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()


class RouterViewHelper(object):
    def __init__(self, router_views_helper, router_key):
        self.router_key = router_key
        self.router_type = router_views_helper.router_type
        self.router_helper = router_views_helper

    def get_view_url(self, view):
        view_def = base_utils.get_router_view_definition(
            self.router_type)
        return view_def.get_view_url(
            view, router_key=self.router_key)

    def get_router(self):
        return self.router_helper.get_router(self.router_key)
