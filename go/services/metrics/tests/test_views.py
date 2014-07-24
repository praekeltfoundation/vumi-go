import cgi
import json

from go.base.tests.helpers import GoDjangoTestCase
from go.services.tests.view_helpers import ServiceComponentViewsHelper
from go.vumitools.api import VumiApiCommand


class MetricsServiceViewTests(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(
            ServiceComponentViewsHelper(u'metrics'))
        self.user_helper = self.service_helper.vumi_helper.get_or_create_user()
        self.client = self.service_helper.get_client()

    def test_new_service_component(self):
        service_store = self.user_helper.user_api.service_component_store
        self.assertEqual([], service_store.list_service_components())

        response = self.client.post(self.service_helper.get_new_view_url(), {
            'name': u"myservice",
            'service_component_type': u'metrics',
        })
        [service_key] = service_store.list_service_components()
        rtr_helper = self.service_helper.get_service_helper_by_key(service_key)
        self.assertRedirects(response, rtr_helper.get_view_url('edit'))

    def test_show_stopped(self):
        svc_helper = self.service_helper.create_service_helper(
            name=u"myservice")
        response = self.client.get(svc_helper.get_view_url('show'))
        service = response.context[0].get('service')
        self.assertEqual(service.name, u"myservice")
        self.assertContains(response, svc_helper.get_view_url('start'))
        self.assertNotContains(response, svc_helper.get_view_url('stop'))

    def test_show_running(self):
        svc_helper = self.service_helper.create_service_helper(
            name=u"myservice", started=True)
        response = self.client.get(svc_helper.get_view_url('show'))
        service = response.context[0].get('service')
        self.assertEqual(service.name, u"myservice")
        self.assertNotContains(response, svc_helper.get_view_url('start'))
        self.assertContains(response, svc_helper.get_view_url('stop'))

    def test_start(self):
        svc_helper = self.service_helper.create_service_helper(started=False)

        response = self.client.post(svc_helper.get_view_url('start'))
        self.assertRedirects(response, svc_helper.get_view_url('show'))
        service = svc_helper.get_service_component()
        self.assertTrue(service.starting())
        [start_cmd] = self.service_helper.get_api_commands_sent()
        self.assertEqual(
            start_cmd, VumiApiCommand.command(
                '%s_service' % (service.service_component_type,), 'start',
                user_account_key=service.user_account.key,
                service_key=service.key))

    def test_stop(self):
        svc_helper = self.service_helper.create_service_helper(started=True)

        response = self.client.post(svc_helper.get_view_url('stop'))
        self.assertRedirects(response, svc_helper.get_view_url('show'))
        service = svc_helper.get_service_component()
        self.assertTrue(service.stopping())
        [start_cmd] = self.service_helper.get_api_commands_sent()
        self.assertEqual(
            start_cmd, VumiApiCommand.command(
                '%s_service' % (service.service_component_type,), 'stop',
                user_account_key=service.user_account.key,
                service_key=service.key))

    def test_get_edit_empty_config(self):
        svc_helper = self.service_helper.create_service_helper(started=True)
        response = self.client.get(svc_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_get_edit_config(self):
        svc_helper = self.service_helper.create_service_helper(
            started=True, config={
                'metrics_prefix': 'mymetrics',
                'metrics': [{'name': 'foo'}, {'name': 'bar'}],
            })
        response = self.client.get(svc_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mymetrics')
        metrics_json = json.dumps([{'name': 'foo'}, {'name': 'bar'}])
        self.assertContains(response, cgi.escape(metrics_json, quote=True))

    def test_edit_service_config(self):
        svc_helper = self.service_helper.create_service_helper(started=True)
        service = svc_helper.get_service_component()
        self.assertEqual(service.config, {})
        response = self.client.post(svc_helper.get_view_url('edit'), {
            'metrics_prefix': ['mymetrics'],
            'metrics_json': ['[{"name": "foo"}, {"name": "bar"}]'],
        })
        self.assertRedirects(response, svc_helper.get_view_url('show'))
        service = svc_helper.get_service_component()
        self.assertEqual(service.config, {
            u'metrics_prefix': u'mymetrics',
            u'metrics': [
                {u'name': u'foo'},
                {u'name': u'bar'},
            ],
        })
