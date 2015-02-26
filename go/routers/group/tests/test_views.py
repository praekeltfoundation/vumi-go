from go.base.tests.helpers import GoDjangoTestCase
from go.routers.tests.view_helpers import RouterViewsHelper
from go.vumitools.api import VumiApiCommand


class GroupViewTests(GoDjangoTestCase):

    def setUp(self):
        self.router_helper = self.add_helper(RouterViewsHelper(u'group'))
        self.user_helper = self.router_helper.vumi_helper.get_or_create_user()
        self.client = self.router_helper.get_client()

    def test_new_router(self):
        router_store = self.user_helper.user_api.router_store
        self.assertEqual([], router_store.list_routers())

        response = self.client.post(self.router_helper.get_new_view_url(), {
            'name': u"myrouter",
            'router_type': u'group',
        })
        [router_key] = router_store.list_routers()
        rtr_helper = self.router_helper.get_router_helper_by_key(router_key)
        self.assertRedirects(response, rtr_helper.get_view_url('edit'))

    def test_show_stopped(self):
        rtr_helper = self.router_helper.create_router_helper(name=u"myrouter")
        response = self.client.get(rtr_helper.get_view_url('show'))
        router = response.context[0].get('router')
        self.assertEqual(router.name, u"myrouter")
        self.assertContains(response, rtr_helper.get_view_url('start'))
        self.assertNotContains(response, rtr_helper.get_view_url('stop'))

    def test_show_running(self):
        rtr_helper = self.router_helper.create_router_helper(
            name=u"myrouter", started=True)
        response = self.client.get(rtr_helper.get_view_url('show'))
        router = response.context[0].get('router')
        self.assertEqual(router.name, u"myrouter")
        self.assertNotContains(response, rtr_helper.get_view_url('start'))
        self.assertContains(response, rtr_helper.get_view_url('stop'))

    def test_start(self):
        rtr_helper = self.router_helper.create_router_helper(started=False)

        response = self.client.post(rtr_helper.get_view_url('start'))
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertTrue(router.starting())
        [start_cmd] = self.router_helper.get_api_commands_sent()
        self.assertEqual(
            start_cmd, VumiApiCommand.command(
                '%s_router' % (router.router_type,), 'start',
                command_id=start_cmd["command_id"],
                user_account_key=router.user_account.key,
                router_key=router.key))

    def test_stop(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)

        response = self.client.post(rtr_helper.get_view_url('stop'))
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertTrue(router.stopping())
        [stop_cmd] = self.router_helper.get_api_commands_sent()
        self.assertEqual(
            stop_cmd, VumiApiCommand.command(
                '%s_router' % (router.router_type,), 'stop',
                command_id=stop_cmd["command_id"],
                user_account_key=router.user_account.key,
                router_key=router.key))

    def test_get_edit_empty_config(self):
        rtr_helper = self.router_helper.create_router_helper(started=True)
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_edit_shows_only_static_groups(self):
        static_group = self.router_helper.create_group(u'staticgroup')
        smart_group = self.router_helper.create_smart_group(u'smartgroup', u'')
        rtr_helper = self.router_helper.create_router_helper(started=True)
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, static_group.key)
        self.assertContains(response, static_group.name)
        self.assertNotContains(response, smart_group.key)
        self.assertNotContains(response, smart_group.name)
        self.assertContains(
            response, "Smart groups are not currently supported")

    def test_get_edit_small_config(self):
        group = self.router_helper.create_group(u'mygroup')
        rtr_helper = self.router_helper.create_router_helper(
            started=True, config={'rules': [
                {
                    'group': group.key,
                    'endpoint': 'target_endpoint',
                },
            ]})
        response = self.client.get(rtr_helper.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, group.name)
        self.assertContains(response, 'target_endpoint')

    def test_edit_router_config(self):
        group1 = self.router_helper.create_group(u'mygroup 1')
        group2 = self.router_helper.create_group(u'mygroup 2')
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'rules-TOTAL_FORMS': ['2'],
            'rules-INITIAL_FORMS': ['0'],
            'rules-MAX_NUM_FORMS': [''],
            'rules-0-group': [group1.key],
            'rules-0-endpoint': ['foo'],
            'rules-0-DELETE': [''],
            'rules-1-group': [group2.key],
            'rules-1-endpoint': ['bar'],
            'rules-1-DELETE': [''],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'rules': [
            {'group': group1.key, 'endpoint': 'foo'},
            {'group': group2.key, 'endpoint': 'bar'},
        ]})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['foo', 'bar']))

    def test_edit_router_group_config_with_delete(self):
        group1 = self.router_helper.create_group(u'mygroup 1')
        group2 = self.router_helper.create_group(u'mygroup 2')
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'rules-TOTAL_FORMS': ['2'],
            'rules-INITIAL_FORMS': ['0'],
            'rules-MAX_NUM_FORMS': [''],
            'rules-0-group': [group1.key],
            'rules-0-endpoint': ['foo'],
            'rules-0-DELETE': ['on'],
            'rules-1-group': [group2.key],
            'rules-1-endpoint': ['bar'],
            'rules-1-DELETE': [''],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'rules': [
            {'group': group2.key, 'endpoint': 'bar'},
        ]})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['bar']))

    def test_edit_router_group_config_with_delete_missing_group(self):
        group = self.router_helper.create_group(u'mygroup')
        rtr_helper = self.router_helper.create_router_helper(started=True)
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {})
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'rules-TOTAL_FORMS': ['2'],
            'rules-INITIAL_FORMS': ['0'],
            'rules-MAX_NUM_FORMS': [''],
            'rules-0-group': ['badgroup'],
            'rules-0-endpoint': ['foo'],
            'rules-0-DELETE': ['on'],
            'rules-1-group': [group.key],
            'rules-1-endpoint': ['bar'],
            'rules-1-DELETE': [''],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'rules': [
            {'group': group.key, 'endpoint': 'bar'},
        ]})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['bar']))

    def test_edit_router_group_config_with_unmodified_extra_form(self):
        group = self.router_helper.create_group(u'mygroup')
        rtr_helper = self.router_helper.create_router_helper(
            started=True, extra_outbound_endpoints=[u'foo'],
            config={u'rules': [{'group': group.key, 'endpoint': 'foo'}]})
        router = rtr_helper.get_router()
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'rules-TOTAL_FORMS': ['2'],
            'rules-INITIAL_FORMS': ['1'],
            'rules-MAX_NUM_FORMS': [''],
            'rules-0-group': [group.key],
            'rules-0-endpoint': ['foo'],
            'rules-0-DELETE': [''],
            'rules-1-group': [''],
            'rules-1-endpoint': [''],
            'rules-1-DELETE': [''],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'rules': [
            {'group': group.key, 'endpoint': 'foo'},
        ]})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['foo']))

    def test_edit_router_group_config_extra_form_empty_group(self):
        group = self.router_helper.create_group(u'mygroup')
        rtr_helper = self.router_helper.create_router_helper(
            started=True, extra_outbound_endpoints=[u'foo'],
            config={u'rules': [{'group': group.key, 'endpoint': 'foo'}]})
        router = rtr_helper.get_router()
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'rules-TOTAL_FORMS': ['2'],
            'rules-INITIAL_FORMS': ['1'],
            'rules-MAX_NUM_FORMS': [''],
            'rules-0-group': [group.key],
            'rules-0-endpoint': ['foo'],
            'rules-0-DELETE': [''],
            'rules-1-group': [''],
            'rules-1-endpoint': ['bar'],
            'rules-1-DELETE': [''],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['edit_forms'][0].errors,
            [{}, {'group': [u'This field is required.']}])
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'rules': [
            {'group': group.key, 'endpoint': 'foo'},
        ]})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['foo']))

    def test_edit_router_group_config_extra_form_empty_endpoint(self):
        group = self.router_helper.create_group(u'mygroup')
        other_group = self.router_helper.create_group(u'othergroup')
        rtr_helper = self.router_helper.create_router_helper(
            started=True, extra_outbound_endpoints=[u'foo'],
            config={u'rules': [{'group': group.key, 'endpoint': 'foo'}]})
        router = rtr_helper.get_router()
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'rules-TOTAL_FORMS': ['2'],
            'rules-INITIAL_FORMS': ['1'],
            'rules-MAX_NUM_FORMS': [''],
            'rules-0-group': [group.key],
            'rules-0-endpoint': ['foo'],
            'rules-0-DELETE': [''],
            'rules-1-group': [other_group.key],
            'rules-1-endpoint': [''],
            'rules-1-DELETE': [''],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['edit_forms'][0].errors,
            [{}, {'endpoint': [u'This field is required.']}])
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'rules': [
            {'group': group.key, 'endpoint': 'foo'},
        ]})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['foo']))

    def test_edit_router_group_config_extra_form_new_entry(self):
        group = self.router_helper.create_group(u'mygroup')
        other_group = self.router_helper.create_group(u'othergroup')
        rtr_helper = self.router_helper.create_router_helper(
            started=True, extra_outbound_endpoints=[u'foo'],
            config={u'rules': [{'group': group.key, 'endpoint': 'foo'}]})
        router = rtr_helper.get_router()
        response = self.client.post(rtr_helper.get_view_url('edit'), {
            'rules-TOTAL_FORMS': ['2'],
            'rules-INITIAL_FORMS': ['1'],
            'rules-MAX_NUM_FORMS': [''],
            'rules-0-group': [group.key],
            'rules-0-endpoint': ['foo'],
            'rules-0-DELETE': [''],
            'rules-1-group': [other_group.key],
            'rules-1-endpoint': ['bar'],
            'rules-1-DELETE': [''],
        })
        self.assertRedirects(response, rtr_helper.get_view_url('show'))
        router = rtr_helper.get_router()
        self.assertEqual(router.config, {u'rules': [
            {'group': group.key, 'endpoint': 'foo'},
            {'group': other_group.key, 'endpoint': 'bar'},
        ]})
        self.assertEqual(set(router.extra_inbound_endpoints), set())
        self.assertEqual(
            set(router.extra_outbound_endpoints), set(['foo', 'bar']))
