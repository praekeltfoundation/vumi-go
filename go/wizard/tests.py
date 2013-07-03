from django.core.urlresolvers import reverse

from go.base.tests.utils import declare_longcode_tags
from go.apps.tests.base import DjangoGoApplicationTestCase


class WizardViewsTestCase(DjangoGoApplicationTestCase):
    # TODO: Stop abusing DjangoGoApplicationTestCase for this.

    def test_get_create_view(self):
        declare_longcode_tags(self.api)
        self.add_tagpool_permission(u'longcode')
        response = self.client.get(reverse('wizard:create'))
        # Check that we have a few conversation types in the response
        self.assertContains(response, 'bulk_message')
        self.assertContains(response, 'subscription')
        # Check that we have a tagpool/tag in the response
        self.assertContains(response, 'longcode:')

    def test_post_create_view_valid(self):
        declare_longcode_tags(self.api)
        self.add_tagpool_permission(u'longcode')
        self.assertEqual(0, len(self.user_api.active_conversations()))
        self.assertEqual(0, len(self.user_api.list_endpoints()))
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'country': 'International',
            'channel': 'longcode:',
        })
        self.assertEqual(1, len(self.user_api.active_conversations()))
        self.assertEqual(1, len(self.user_api.list_endpoints()))
        conv = self.get_latest_conversation()
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
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'country': 'International',
            'channel': 'badpool:',
        })
        # TODO: Test that we do the right thing with the bad form when we do
        #       the right thing with the bad form.
        self.assertEqual(response.status_code, 200)
