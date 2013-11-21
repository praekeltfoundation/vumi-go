from django.core.urlresolvers import reverse

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.vumitools.routing_table import RoutingTable


class TestWizardViews(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = DjangoVumiApiHelper()
        self.add_cleanup(self.vumi_helper.cleanup)
        self.vumi_helper.setup_vumi_api()
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def assert_stored_models(self, channels=[], routers=[], convs=[]):
        user_api = self.user_helper.user_api
        self.assertEqual([ch.key for ch in channels],
                         [ch.key for ch in user_api.active_channels()])
        self.assertEqual([r.key for r in routers],
                         [r.key for r in user_api.active_routers()])
        self.assertEqual([c.key for c in convs],
                         [c.key for c in user_api.active_conversations()])

    def assert_routing_table(self, channel_conv=[], channel_router=[],
                             router_conv=[]):
        """Assert that the routing table has a particular form.

        :param tag_conv: List of (tag, conversation) pairs.
        :param tag_router: List of (tag, router) pairs.
        :param router_conv: List of (router, endpoint, conversation) triples.
        """
        rt = RoutingTable()
        for channel, conv in channel_conv:
            channel_conn = channel.get_connector()
            conv_conn = conv.get_connector()
            rt.add_entry(channel_conn, 'default', conv_conn, 'default')
            rt.add_entry(conv_conn, 'default', channel_conn, 'default')

        for channel, router in channel_router:
            channel_conn = channel.get_connector()
            rin_conn = router.get_inbound_connector()
            rt.add_entry(channel_conn, 'default', rin_conn, 'default')
            rt.add_entry(rin_conn, 'default', channel_conn, 'default')

        for router, endpoint, conv in router_conv:
            rout_conn = router.get_outbound_connector()
            conv_conn = conv.get_connector()
            rt.add_entry(rout_conn, endpoint, conv_conn, 'default')
            rt.add_entry(conv_conn, 'default', rout_conn, endpoint)

        self.assertEqual(self.user_helper.user_api.get_routing_table(), rt)

    def test_get_create_view(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.user_helper.add_app_permission(u'go.apps.subscription')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        response = self.client.get(reverse('wizard:create'))
        # Check that we have a few conversation types in the response
        self.assertContains(response, 'bulk_message')
        self.assertContains(response, 'subscription')
        self.assertNotContains(response, 'survey')
        # Check that we have a tagpool/tag in the response
        self.assertContains(response, 'longcode:')

    def test_get_create_view_with_existing_routers(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.user_helper.add_app_permission(u'go.apps.subscription')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.user_helper.create_router(u"dummy", name=u"non-kw-router")
        self.user_helper.create_router(u"keyword", name=u"existing-kw-router")
        response = self.client.get(reverse('wizard:create'))
        # Check that we have a few conversation types in the response
        self.assertContains(response, 'bulk_message')
        self.assertContains(response, 'subscription')
        self.assertNotContains(response, 'survey')
        self.assertContains(response, 'existing-kw-router')
        self.assertNotContains(response, 'non-kw-router')
        # Check that we have a tagpool/tag in the response
        self.assertContains(response, 'longcode:')

    def test_post_create_view_valid(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
        })

        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        self.assertEqual([], self.user_helper.user_api.active_routers())

        [channel] = self.user_helper.user_api.active_channels()
        self.assertEqual(u'longcode:tag1', channel.key)

        self.assert_routing_table(channel_conv=[(channel, conv)])

    def test_post_create_view_specific_tag(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'], metadata={
                'user_selects_tag': True,
            })
        self.user_helper.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:tag1',
        })

        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        self.assertEqual([], self.user_helper.user_api.active_routers())

        [channel] = self.user_helper.user_api.active_channels()
        self.assertEqual(u'longcode:tag1', channel.key)

        self.assert_routing_table(channel_conv=[(channel, conv)])

    def test_post_create_view_editable_conversation(self):
        self.user_helper.add_app_permission(u'go.apps.jsbox')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'jsbox',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
        })
        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual(1, len(self.user_helper.user_api.active_channels()))
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': 'edit/',
            }))

    def test_post_create_view_extra_endpoints(self):
        self.user_helper.add_app_permission(u'go.apps.wikipedia')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'wikipedia',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
        })
        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual(list(conv.extra_endpoints), [u'sms_content'])
        self.assertEqual(1, len(self.user_helper.user_api.active_channels()))
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

    def test_post_create_view_invalid_conversation_type(self):
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'foo',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
        })
        self.assert_stored_models()
        # TODO: Test that we do the right thing with the bad form when we do
        #       the right thing with the bad form.
        self.assertEqual(response.status_code, 200)

    def test_post_create_view_invalid_country(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'Nowhere',
            'channel': 'longcode:',
        })
        self.assert_stored_models()
        # TODO: Test that we do the right thing with the bad form when we do
        #       the right thing with the bad form.
        self.assertEqual(response.status_code, 200)

    def test_post_create_view_invalid_channel(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'badpool:',
        })
        self.assert_stored_models()
        # TODO: Test that we do the right thing with the bad form when we do
        #       the right thing with the bad form.
        self.assertEqual(response.status_code, 200)

    def test_post_create_view_with_keyword(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
            'keyword': 'foo',
        })

        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        [router] = self.user_helper.user_api.active_routers()
        self.assertEqual('keyword', router.router_type)
        self.assertEqual('Keywords for longcode:tag1', router.name)
        self.assertEqual(
            ['keyword_foo'], list(router.extra_outbound_endpoints))
        self.assertEqual({
            'keyword_endpoint_mapping': {'foo': 'keyword_foo'},
        }, router.config)
        self.assertTrue(router.running() or router.starting())

        [channel] = self.user_helper.user_api.active_channels()
        self.assertEqual(u'longcode:tag1', channel.key)

        self.assert_routing_table(
            channel_router=[(channel, router)],
            router_conv=[(router, 'keyword_foo', conv)])

    def test_post_create_view_with_keyword_default(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
            'keyword': 'default',
        })

        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        [router] = self.user_helper.user_api.active_routers()
        self.assertEqual('keyword', router.router_type)
        self.assertEqual('Keywords for longcode:tag1', router.name)
        self.assertEqual(
            ['keyword_default'], list(router.extra_outbound_endpoints))
        self.assertEqual({
            'keyword_endpoint_mapping': {'default': 'keyword_default'},
        }, router.config)
        self.assertTrue(router.running() or router.starting())

        [channel] = self.user_helper.user_api.active_channels()
        self.assertEqual(u'longcode:tag1', channel.key)

        self.assert_routing_table(
            channel_router=[(channel, router)],
            router_conv=[(router, 'keyword_default', conv)])

    def test_post_create_view_with_existing_router(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        existing_router = self.user_helper.create_router(u"keyword")
        self.assert_stored_models(routers=[existing_router])
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'existing',
            'existing_router': existing_router.key,
            'new_keyword': 'foo',
        })

        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        [router] = self.user_helper.user_api.active_routers()
        self.assertEqual(existing_router.key, router.key)
        self.assertEqual(
            ['keyword_foo'], list(router.extra_outbound_endpoints))
        self.assertEqual({
            'keyword_endpoint_mapping': {'foo': 'keyword_foo'},
        }, router.config)

        self.assert_stored_models(routers=[existing_router], convs=[conv])
        self.assert_routing_table(router_conv=[(router, 'keyword_foo', conv)])

    def test_post_create_view_with_existing_keyword(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        existing_router = self.user_helper.create_router(u"keyword", config={
            'keyword_endpoint_mapping': {'foo': 'keyword_foo'},
        })
        self.assert_stored_models(routers=[existing_router])
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'existing',
            'existing_router': existing_router.key,
            'new_keyword': 'foo',
        })

        self.assert_stored_models(routers=[existing_router])
        # TODO: Test that we do the right thing with the bad form when we do
        #       the right thing with the bad form.
        self.assertEqual(response.status_code, 200)
