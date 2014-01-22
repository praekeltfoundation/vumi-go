from django.core.urlresolvers import reverse

from go.base.tests.helpers import GoDjangoTestCase

from go.services import settings

from .helpers import ServiceViewHelper
from .dummy.view_definition import DummyServiceView, DummyServiceViewNoSuffix


class TestServiceViews(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(settings, 'INSTALLED_SERVICES', {
            'go.services.tests.dummy': {
                'namespace': 'dummy',
                'display_name': 'Dummy service',
            },
        })

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
