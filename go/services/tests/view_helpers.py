from django.core.urlresolvers import reverse

from zope.interface import implements

from vumi.tests.helpers import generate_proxies, IHelper

from go.base import utils as base_utils
from go.base.tests.helpers import DjangoVumiApiHelper
from .helpers import ServiceHelper


class ServiceComponentViewsHelper(object):
    implements(IHelper)

    def __init__(self, service_type):
        self.service_type = service_type

        self.vumi_helper = DjangoVumiApiHelper()
        self._service_helper = ServiceHelper(service_type, self.vumi_helper)

        # Proxy methods from our helpers.
        generate_proxies(self, self._service_helper)
        generate_proxies(self, self.vumi_helper)

    def setup(self):
        self.vumi_helper.setup()
        self.vumi_helper.make_django_user()

    def cleanup(self):
        return self.vumi_helper.cleanup()

    def get_new_view_url(self):
        return reverse('services:new_service')

    def get_service_helper(self, service):
        return self.get_service_helper_by_key(service.key)

    def create_service_helper(self, *args, **kw):
        service = self.create_service_component(*args, **kw)
        return self.get_service_helper(service)

    def get_service_helper_by_key(self, service_key):
        return ServiceViewHelper(self, service_key)

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()


class ServiceViewHelper(object):
    def __init__(self, service_views_helper, service_key):
        self.service_key = service_key
        self.service_type = service_views_helper.service_type
        self.service_helper = service_views_helper

    def get_view_url(self, view):
        view_def = base_utils.get_service_view_definition(
            self.service_type)
        return view_def.get_view_url(
            view, service_key=self.service_key)

    def get_service_component(self):
        return self.service_helper.get_service_component(self.service_key)
