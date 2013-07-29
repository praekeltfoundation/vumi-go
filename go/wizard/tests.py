from django.core.urlresolvers import reverse

from go.base.tests.utils import VumiGoDjangoTestCase
from go.vumitools.account import GoConnector


class WizardViewsTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(WizardViewsTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

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

    def test_post_create_view_valid(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assertEqual([], self.user_api.active_conversations())
        self.assertEqual([], self.user_api.active_routers())
        self.assertEqual(set(), self.user_api.list_endpoints())
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
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

        conv_conn = str(
            GoConnector.for_conversation(conv.conversation_type, conv.key))
        tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
        self.assertEqual(self.user_api.get_routing_table(), {
            conv_conn: {u'default': [tag_conn, u'default']},
            tag_conn: {u'default': [conv_conn, u'default']},
        })

    def test_post_create_view_editable_conversation(self):
        self.add_app_permission(u'go.apps.jsbox')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assertEqual(0, len(self.user_api.active_conversations()))
        self.assertEqual(0, len(self.user_api.list_endpoints()))
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'jsbox',
            'name': 'My Conversation',
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
        self.assertEqual(0, len(self.user_api.active_conversations()))
        self.assertEqual(0, len(self.user_api.list_endpoints()))
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'wikipedia',
            'name': 'My Conversation',
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
            'country': 'International',
            'channel': 'longcode:',
        })
        # TODO: Test that we do the right thing with the bad form when we do
        #       the right thing with the bad form.
        self.assertEqual(response.status_code, 200)

    def test_post_create_view_invalid_country(self):
        self.add_app_permission(u'go.apps.bulk_message')
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'country': 'Nowhere',
            'channel': 'longcode:',
        })
        # TODO: Test that we do the right thing with the bad form when we do
        #       the right thing with the bad form.
        self.assertEqual(response.status_code, 200)

    def test_post_create_view_invalid_channel(self):
        self.add_app_permission(u'go.apps.bulk_message')
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'country': 'International',
            'channel': 'badpool:',
        })
        # TODO: Test that we do the right thing with the bad form when we do
        #       the right thing with the bad form.
        self.assertEqual(response.status_code, 200)

    def test_post_create_view_with_keyword(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assertEqual([], self.user_api.active_conversations())
        self.assertEqual([], self.user_api.active_routers())
        self.assertEqual(set(), self.user_api.list_endpoints())
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
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
        self.assertEqual('My Conversation router', router.name)
        self.assertEqual(['foo'], list(router.extra_inbound_endpoints))
        self.assertEqual({
            'keyword_endpoint_mapping': {'foo': 'foo'},
        }, router.config)

        [tag] = list(self.user_api.list_endpoints())
        self.assertEqual((u'longcode', u'default10001'), tag)

        conv_conn = str(
            GoConnector.for_conversation(conv.conversation_type, conv.key))
        tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
        rin_conn = str(
            GoConnector.for_router(
                router.router_type, router.key, GoConnector.INBOUND))
        rout_conn = str(
            GoConnector.for_router(
                router.router_type, router.key, GoConnector.OUTBOUND))
        self.assertEqual(self.user_api.get_routing_table(), {
            conv_conn: {u'default': [rin_conn, u'foo']},
            tag_conn: {u'default': [rout_conn, u'default']},
            rin_conn: {u'foo': [conv_conn, u'default']},
            rout_conn: {u'default': [tag_conn, u'default']},
        })

    def test_post_create_view_with_keyword_default(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assertEqual([], self.user_api.active_conversations())
        self.assertEqual([], self.user_api.active_routers())
        self.assertEqual(set(), self.user_api.list_endpoints())
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
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
        self.assertEqual('My Conversation router', router.name)
        self.assertEqual([], list(router.extra_inbound_endpoints))
        self.assertEqual({
            'keyword_endpoint_mapping': {'default': 'default'},
        }, router.config)

        [tag] = list(self.user_api.list_endpoints())
        self.assertEqual((u'longcode', u'default10001'), tag)

        conv_conn = str(
            GoConnector.for_conversation(conv.conversation_type, conv.key))
        tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
        rin_conn = str(
            GoConnector.for_router(
                router.router_type, router.key, GoConnector.INBOUND))
        rout_conn = str(
            GoConnector.for_router(
                router.router_type, router.key, GoConnector.OUTBOUND))
        self.assertEqual(self.user_api.get_routing_table(), {
            conv_conn: {u'default': [rin_conn, u'default']},
            tag_conn: {u'default': [rout_conn, u'default']},
            rin_conn: {u'default': [conv_conn, u'default']},
            rout_conn: {u'default': [tag_conn, u'default']},
        })
