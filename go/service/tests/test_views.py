import urllib

from django import forms
from django.core.urlresolvers import reverse

import go.base.utils
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.service.view_definition import (
    EditServiceComponentView, ServiceComponentViewDefinitionBase)
from go.vumitools.service.definition import ServiceComponentDefinitionBase


class DummyServiceDefinition(ServiceComponentDefinitionBase):
    service_component_type = 'dummy'
    service_component_display_name = 'Dummy Service Component'


class SimpleEditForm(forms.Form):
    simple_field = forms.CharField()


class SimpleEditView(EditServiceComponentView):
    edit_forms = (
        (None, SimpleEditForm),
    )


class EditableServiceDefinition(ServiceComponentDefinitionBase):
    service_component_type = 'editable'
    service_component_display_name = 'Simple Editable Service Component'


class EditableServiceViewDefinition(ServiceComponentViewDefinitionBase):
    edit_view = SimpleEditView


DUMMY_SERVICE_DEFS = {
    'dummy': (DummyServiceDefinition, ServiceComponentViewDefinitionBase),
    'editable': (EditableServiceDefinition, EditableServiceViewDefinition),
}


DUMMY_SERVICE_SETTINGS = dict([
    ('gotest.' + app, {
        'namespace': app,
        'display_name': defs[0].service_component_display_name,
    }) for app, defs in DUMMY_SERVICE_DEFS.items()])


class FakeServicePackage(object):
    """Pretends to be a package containing modules and classes for an app.
    """
    def __init__(self, service_type):
        self.definition = self
        self.view_definition = self
        def_cls, vdef_cls = DUMMY_SERVICE_DEFS[service_type]
        self.ServiceComponentDefinition = def_cls
        self.ServiceComponentViewDefinition = vdef_cls


class TestServiceComponentViews(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.monkey_patch(
            go.base.utils, 'get_service_pkg', self._get_service_pkg)
        self.vumi_helper.patch_config(
            VUMI_INSTALLED_SERVICES=DUMMY_SERVICE_SETTINGS)
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def _get_service_pkg(self, service_type, from_list=()):
        """Test stub for `go.base.utils.get_service_pkg()`
        """
        return FakeServicePackage(service_type)

    def get_view_url(self, service, view):
        view_def = go.base.utils.get_service_view_definition(
            service.service_component_type)
        return view_def.get_view_url(view, service_key=service.key)

    def test_index(self):
        service = self.user_helper.create_service_component(u'dummy')
        archived_service = self.user_helper.create_service_component(
            u'dummy', name=u'archived', archived=True)
        response = self.client.get(reverse('services:index'))
        self.assertContains(response, urllib.quote(service.key))
        self.assertNotContains(response, urllib.quote(archived_service.key))

    def test_get_new_service(self):
        response = self.client.get(reverse('services:new_service'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Service component name')
        self.assertContains(response, 'kind of service component')
        self.assertContains(response, 'dummy')
        self.assertNotContains(response, 'bulk_message')

    def test_post_new_service(self):
        form_data = {
            'name': 'new service component',
            'service_component_type': 'dummy',
        }
        response = self.client.post(reverse('services:new_service'), form_data)
        [service] = self.user_helper.user_api.active_service_components()
        self.assertRedirects(response, self.get_view_url(service, 'show'))
        self.assertEqual(service.name, 'new service component')
        self.assertEqual(service.service_component_type, 'dummy')

    def test_post_new_editable_service(self):
        form_data = {
            'name': 'new service component',
            'service_component_type': 'editable',
        }
        response = self.client.post(reverse('services:new_service'), form_data)
        [service] = self.user_helper.user_api.active_service_components()
        self.assertRedirects(response, self.get_view_url(service, 'edit'))
        self.assertEqual(service.name, 'new service component')
        self.assertEqual(service.service_component_type, 'editable')
