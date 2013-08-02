from django.core.urlresolvers import reverse

from go.base.tests.utils import VumiGoDjangoTestCase
from go.vumitools.account import RoutingTableHelper, GoConnector


class WizardViewsTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(WizardViewsTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def assert_stored_models(self, tags=[], routers=[], convs=[]):
        self.assertEqual(set(tags), self.user_api.list_endpoints())
        self.assertEqual([r.key for r in routers],
                         [r.key for r in self.user_api.active_routers()])
        self.assertEqual([c.key for c in convs],
                         [c.key for c in self.user_api.active_conversations()])

    def assert_routing_table(self, tag_conv=[], tag_router=[], router_conv=[]):
        """Assert that the routing table has a particular form.

        :param tag_conv: List of (tag, conversation) pairs.
        :param tag_router: List of (tag, router) pairs.
        :param router_conv: List of (router, endpoint, conversation) triples.
        """
        rt = RoutingTableHelper({})
        for tag, conv in tag_conv:
            tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
            conv_conn = str(GoConnector.for_conversation(
                conv.conversation_type, conv.key))
            rt.add_entry(tag_conn, 'default', conv_conn, 'default')
            rt.add_entry(conv_conn, 'default', tag_conn, 'default')

        for tag, router in tag_router:
            tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
            rin_conn = str(GoConnector.for_router(
                router.router_type, router.key, GoConnector.INBOUND))
            rt.add_entry(tag_conn, 'default', rin_conn, 'default')
            rt.add_entry(rin_conn, 'default', tag_conn, 'default')

        for router, endpoint, conv in router_conv:
            rout_conn = str(GoConnector.for_router(
                router.router_type, router.key, GoConnector.OUTBOUND))
            conv_conn = str(GoConnector.for_conversation(
                conv.conversation_type, conv.key))
            rt.add_entry(rout_conn, endpoint, conv_conn, 'default')
            rt.add_entry(conv_conn, 'default', rout_conn, endpoint)

        self.assertEqual(self.user_api.get_routing_table(), rt.routing_table)

    def test_get_create_view(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.add_app_permission(u'go.apps.subscription')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        response = self.client.get(reverse('wizard:create'))
        # Check that we have a few conversation types in the response
        self.assertContains(response, 'bulk_message')
        self.assertContains(response, 'subscription')
        self.assertNotContains(response, 'survey')
        # Check that we have a tagpool/tag in the response
        self.assertContains(response, 'longcode:')

    def test_get_create_view_with_existing_routers(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.add_app_permission(u'go.apps.subscription')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.create_router(name=u"non-kw-router")
        self.create_router(name=u"existing-kw-router", router_type=u"keyword")
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
        self.add_app_permission(u'go.apps.bulk_message')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
        })

        [conv] = self.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        self.assertEqual([], self.user_api.active_routers())

        [tag] = list(self.user_api.list_endpoints())
        self.assertEqual((u'longcode', u'default10001'), tag)

        self.assert_routing_table(tag_conv=[(tag, conv)])

    def test_post_create_view_editable_conversation(self):
        self.add_app_permission(u'go.apps.jsbox')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'jsbox',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
        })
        [conv] = self.user_api.active_conversations()
        self.assertEqual(1, len(self.user_api.list_endpoints()))
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': 'edit/',
            }))

    def test_post_create_view_extra_endpoints(self):
        self.add_app_permission(u'go.apps.wikipedia')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'wikipedia',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
        })
        [conv] = self.user_api.active_conversations()
        self.assertEqual(list(conv.extra_endpoints), [u'sms_content'])
        self.assertEqual(1, len(self.user_api.list_endpoints()))
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
        self.add_app_permission(u'go.apps.bulk_message')
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
        self.add_app_permission(u'go.apps.bulk_message')
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
        self.add_app_permission(u'go.apps.bulk_message')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
            'keyword': 'foo',
        })

        [conv] = self.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        [router] = self.user_api.active_routers()
        self.assertEqual('keyword', router.router_type)
        self.assertEqual('Keywords for longcode:default10001', router.name)
        self.assertEqual(
            ['keyword_foo'], list(router.extra_outbound_endpoints))
        self.assertEqual({
            'keyword_endpoint_mapping': {'foo': 'keyword_foo'},
        }, router.config)

        [tag] = list(self.user_api.list_endpoints())
        self.assertEqual((u'longcode', u'default10001'), tag)

        self.assert_routing_table(
            tag_router=[(tag, router)],
            router_conv=[(router, 'keyword_foo', conv)])

    def test_post_create_view_with_keyword_default(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'new',
            'country': 'International',
            'channel': 'longcode:',
            'keyword': 'default',
        })

        [conv] = self.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        [router] = self.user_api.active_routers()
        self.assertEqual('keyword', router.router_type)
        self.assertEqual('Keywords for longcode:default10001', router.name)
        self.assertEqual(
            ['keyword_default'], list(router.extra_outbound_endpoints))
        self.assertEqual({
            'keyword_endpoint_mapping': {'default': 'keyword_default'},
        }, router.config)

        [tag] = list(self.user_api.list_endpoints())
        self.assertEqual((u'longcode', u'default10001'), tag)

        self.assert_routing_table(
            tag_router=[(tag, router)],
            router_conv=[(router, 'keyword_default', conv)])

    def test_post_create_view_with_existing_router(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        existing_router = self.create_router(router_type=u"keyword")
        self.assert_stored_models(routers=[existing_router])
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'channel_kind': 'existing',
            'existing_router': existing_router.key,
            'new_keyword': 'foo',
        })

        [conv] = self.user_api.active_conversations()
        self.assertEqual('bulk_message', conv.conversation_type)
        self.assertEqual('My Conversation', conv.name)
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

        [router] = self.user_api.active_routers()
        self.assertEqual(existing_router.key, router.key)
        self.assertEqual(
            ['keyword_foo'], list(router.extra_outbound_endpoints))
        self.assertEqual({
            'keyword_endpoint_mapping': {'foo': 'keyword_foo'},
        }, router.config)

        self.assert_stored_models(routers=[existing_router], convs=[conv])
        self.assert_routing_table(router_conv=[(router, 'keyword_foo', conv)])

    def test_post_create_view_with_existing_keyword(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        existing_router = self.create_router(router_type=u"keyword", config={
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
