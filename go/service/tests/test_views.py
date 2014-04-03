from django.core.urlresolvers import reverse
from django.http import HttpResponse

import go.base.utils
from go.base.tests.helpers import GoDjangoTestCase
from go.vumitools.service.definition import ServiceDefinitionBase
from go.service.tests.helpers import ServiceViewHelper
from go.service.view_definition import ServiceView, ServiceViewDefinitionBase


class DummyServiceDefinition(ServiceDefinitionBase):
    service_type = u"dummy"
    service_display_name = u"Dummy service"


class DummyServiceView(ServiceView):
    view_name = 'dummy_view'
    path_suffix = 'dummy_suffix'

    def get(self, request):
        return HttpResponse(self.view_name)


class DummyServiceViewNoSuffix(ServiceView):
    view_name = 'dummy_view_no_suffix'
    path_suffix = None

    def get(self, request):
        return HttpResponse(self.view_name)


class DummyServiceViewDefinition(ServiceViewDefinitionBase):
    views = (
        DummyServiceView,
        DummyServiceViewNoSuffix,
    )


DUMMY_SERVICE_DEFS = {
    'dummy': (DummyServiceDefinition, DummyServiceViewDefinition),
}


DUMMY_SERVICE_SETTINGS = dict([
    ('gotest.' + app, {
        'namespace': app,
        'display_name': defs[0].service_display_name,
    }) for app, defs in DUMMY_SERVICE_DEFS.items()])


class FakeServicePackage(object):
    """Pretends to be a package containing modules and classes for an app.
    """
    def __init__(self, service_type):
        self.definition = self
        self.view_definition = self
        def_cls, vdef_cls = DUMMY_SERVICE_DEFS[service_type]
        self.ServiceDefinition = def_cls
        self.ServiceViewDefinition = vdef_cls


class TestServiceViews(GoDjangoTestCase):
    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.monkey_patch(
            go.base.utils, 'get_service_pkg', self._get_service_pkg)
        self.service_helper.patch_config(
            VUMI_INSTALLED_SERVICES=DUMMY_SERVICE_SETTINGS)
        self.client = self.service_helper.get_client()

    def _get_service_pkg(self, service_type, from_list=()):
        """Test stub for `go.base.utils.get_service_pkg()`
        """
        return FakeServicePackage(service_type)

    def test_dummy_service_view(self):
        url = reverse('services:service_index',
                      kwargs={'service_type': 'dummy'})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, DummyServiceView.view_name)

    def test_dummy_service_view_no_suffix(self):
        url = reverse('services:service_index',
                      kwargs={'service_type': 'dummy'})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, DummyServiceViewNoSuffix.view_name)
