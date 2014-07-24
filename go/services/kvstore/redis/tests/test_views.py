from go.base.tests.helpers import GoDjangoTestCase
from go.services.tests.view_helpers import ServiceComponentViewsHelper
from go.vumitools.api import VumiApiCommand


class RedisKVStoreViewTests(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(
            ServiceComponentViewsHelper(u'kvstore.redis'))
        self.user_helper = self.service_helper.vumi_helper.get_or_create_user()
        self.client = self.service_helper.get_client()

    def test_new_service_component(self):
        service_store = self.user_helper.user_api.service_component_store
        self.assertEqual([], service_store.list_service_components())

        response = self.client.post(self.service_helper.get_new_view_url(), {
            'name': u"myservice",
            'service_component_type': u'kvstore.redis',
        })
        [service_key] = service_store.list_service_components()
        svc_helper = self.service_helper.get_service_helper_by_key(service_key)
        self.assertRedirects(response, svc_helper.get_view_url('edit'))

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
            started=True, config={'key_expiry_time': 13370})
        response = self.client.get(svc_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '13370')

    def test_edit_service_keyword_config(self):
        svc_helper = self.service_helper.create_service_helper(started=True)
        service = svc_helper.get_service_component()
        self.assertEqual(service.config, {})
        response = self.client.post(svc_helper.get_view_url('edit'), {
            'key_expiry_time': ['13370'],
        })
        self.assertRedirects(response, svc_helper.get_view_url('show'))
        service = svc_helper.get_service_component()
        self.assertEqual(service.config, {u'key_expiry_time': 13370})
