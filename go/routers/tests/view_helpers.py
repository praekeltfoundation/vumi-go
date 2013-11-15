from django.core.urlresolvers import reverse

from vumi.tests.helpers import generate_proxies

from go.base import utils as base_utils
from go.base.tests.helpers import DjangoVumiApiHelper
from go.vumitools.tests.helpers import GoMessageHelper
from .helpers import RouterHelper


class RouterViewsHelper(object):
    def __init__(self, router_type):
        self.router_type = router_type

        self.vumi_helper = DjangoVumiApiHelper()
        self._app_helper = RouterHelper(
            router_type, self.vumi_helper)
        self._app_helper.router_wrapper = self.get_router_helper

        # Create the things we need to create
        self.vumi_helper.setup_vumi_api()
        self.vumi_helper.make_django_user()

        # Proxy methods from our helpers.
        generate_proxies(self, self._app_helper)
        generate_proxies(self, self.vumi_helper)

    def cleanup(self):
        return self.vumi_helper.cleanup()

    def get_new_view_url(self):
        return reverse('routers:new_router')

    def get_router_helper(self, router):
        return self.get_router_helper_by_key(router.key)

    def get_router_helper_by_key(self, router_key):
        return RouterViewHelper(self, router_key)

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()


class RouterViewHelper(object):
    def __init__(self, router_views_helper, router_key):
        self.router_key = router_key
        self.router_type = router_views_helper.router_type
        self.app_helper = router_views_helper

    def get_view_url(self, view):
        view_def = base_utils.get_router_view_definition(
            self.router_type)
        return view_def.get_view_url(
            view, router_key=self.router_key)

    def get_router(self):
        return self.app_helper.get_router(self.router_key)

    def add_stored_inbound(self, count, **kw):
        msg_helper = GoMessageHelper(mdb=self.app_helper.get_vumi_api().mdb)
        conv = self.get_router()
        return msg_helper.add_inbound_to_conv(conv, count, **kw)

    def add_stored_replies(self, msgs):
        msg_helper = GoMessageHelper(mdb=self.app_helper.get_vumi_api().mdb)
        conv = self.get_router()
        return msg_helper.add_replies_to_conv(conv, msgs)
