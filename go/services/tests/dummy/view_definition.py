from django.http import HttpResponse

from go.services.view_definition import ServiceView, ServiceViewDefinitionBase


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


class ServiceViewDefinition(ServiceViewDefinitionBase):

    views = (
        DummyServiceView,
        DummyServiceViewNoSuffix,
    )
