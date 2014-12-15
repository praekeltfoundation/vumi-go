from django.core.urlresolvers import reverse

import go.config
from go.base.utils import get_conversation_pkg
from go.conversation.view_definition import ConversationViewDefinitionBase
from go.vumitools.conversation.definition import ConversationDefinitionBase
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.vumitools.routing_table import RoutingTable


class DefaultConfigConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'default_config'
    conversation_display_name = 'Default Config Conversation'

    def get_default_config(self, name, description):
        return {
            'name': name,
            'description': description,
        }


DUMMY_CONVERSATION_DEFS = {
    'default_config': (
        DefaultConfigConversationDefinition,
        ConversationViewDefinitionBase)
}


DUMMY_CONVERSATION_SETTINGS = go.config._VUMI_INSTALLED_APPS.copy()
DUMMY_CONVERSATION_SETTINGS.update(dict([
    ('gotest.' + app, {
        'namespace': app,
        'display_name': defs[0].conversation_display_name,
    }) for app, defs in DUMMY_CONVERSATION_DEFS.items()]))


class FakeConversationPackage(object):
    """Pretends to be a package containing modules and classes for an app.
    """
    def __init__(self, conversation_type):
        self.definition = self
        self.view_definition = self
        def_cls, vdef_cls = DUMMY_CONVERSATION_DEFS[conversation_type]
        self.ConversationDefinition = def_cls
        self.ConversationViewDefinition = vdef_cls


class TestWizardViews(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper(), setup_vumi_api=False)
        self.vumi_helper.patch_config(
            VUMI_INSTALLED_APPS=DUMMY_CONVERSATION_SETTINGS)

        self.monkey_patch(
            go.base.utils, 'get_conversation_pkg', self.get_conversation_pkg)

        self.vumi_helper.setup_vumi_api()
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def get_conversation_pkg(self, conversation_type, from_list=()):
        if conversation_type in DUMMY_CONVERSATION_DEFS:
            return FakeConversationPackage(conversation_type)
        return get_conversation_pkg(conversation_type, from_list)

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

    def test_get_create_view_emtpy_or_exhausted_tagpool(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.user_helper.add_app_permission(u'go.apps.subscription')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.vumi_helper.setup_tagpool(u'empty', [])
        self.vumi_helper.setup_tagpool(u'exhausted', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.user_helper.add_tagpool_permission(u'empty')
        self.user_helper.add_tagpool_permission(u'exhausted')
        self.user_helper.user_api.acquire_tag(u'exhausted')
        response = self.client.get(reverse('wizard:create'))
        # Check that we have a few conversation types in the response
        self.assertContains(response, 'bulk_message')
        self.assertContains(response, 'subscription')
        self.assertNotContains(response, 'survey')
        # Check that we have a tagpool/tag in the response
        self.assertContains(response, 'longcode:')
        # Check that we don't have the empty or exhausted tagpools in the
        # response
        self.assertNotContains(response, 'empty:')
        self.assertNotContains(response, 'exhausted:')

    def test_post_create_view_valid(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.assert_stored_models()
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
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
            'country': 'International',
            'channel': 'longcode:',
        })
        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual(list(conv.extra_endpoints), [u'sms_content'])
        self.assertEqual(1, len(self.user_helper.user_api.active_channels()))
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': 'edit/',
            }))

    def test_post_create_view_invalid_conversation_type(self):
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'foo',
            'name': 'My Conversation',
            'country': 'International',
            'channel': 'longcode:',
        })
        self.assert_stored_models()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['conversation_form'].errors, {
                'conversation_type': [
                    u'Select a valid choice. foo is not one of the'
                    u' available choices.']})

    def test_post_create_view_invalid_country(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'country': 'Nowhere',
            'channel': 'longcode:',
        })
        self.assert_stored_models()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['channel_form'].errors, {
                'country': [
                    u'Select a valid choice. Nowhere is not one of the'
                    u' available choices.']})

    def test_post_create_view_invalid_channel(self):
        self.user_helper.add_app_permission(u'go.apps.bulk_message')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'country': 'International',
            'channel': 'badpool:',
        })
        self.assert_stored_models()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['channel_form'].errors, {
                'channel': [
                    u'Select a valid choice. badpool: is not one of the'
                    u' available choices.']})

    def test_post_new_conversation_default_config(self):
        self.user_helper.add_app_permission(u'gotest.default_config')
        self.vumi_helper.setup_tagpool(u'longcode', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'longcode')

        conv_data = {
            'name': 'new conv',
            'description': 'a new conversation',
            'conversation_type': 'default_config',
            'country': 'International',
            'channel': 'longcode:',
        }
        self.client.post(reverse('wizard:create'), conv_data)
        [conv] = self.user_helper.user_api.active_conversations()

        self.assertEqual(conv.config, {
            'name': 'new conv',
            'description': 'a new conversation'
        })
