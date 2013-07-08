from django.core.urlresolvers import reverse

from go.base.tests.utils import VumiGoDjangoTestCase


class WizardViewsTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(WizardViewsTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def test_get_create_view(self):
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        response = self.client.get(reverse('wizard:create'))
        # Check that we have a few conversation types in the response
        self.assertContains(response, 'bulk_message')
        self.assertContains(response, 'subscription')
        # Check that we have a tagpool/tag in the response
        self.assertContains(response, 'longcode:')

    def test_post_create_view_valid(self):
        self.declare_tags(u'longcode', 4)
        self.add_tagpool_permission(u'longcode')
        self.assertEqual(0, len(self.user_api.active_conversations()))
        self.assertEqual(0, len(self.user_api.list_endpoints()))
        response = self.client.post(reverse('wizard:create'), {
            'conversation_type': 'bulk_message',
            'name': 'My Conversation',
            'country': 'International',
            'channel': 'longcode:',
        })
        [conv] = self.user_api.active_conversations()
        self.assertEqual(1, len(self.user_api.list_endpoints()))
        self.assertRedirects(
            response, reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': '',
            }))

    def test_post_create_view_extra_endpoints(self):
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
