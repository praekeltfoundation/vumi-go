from django.core.urlresolvers import reverse
from django.utils.unittest import skip

from go.base.tests.utils import VumiGoDjangoTestCase
from go.conversation.templatetags.conversation_tags import scrub_tokens


def newest(models):
    return max(models, key=lambda m: m.created_at)


class ConversationTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(ConversationTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def test_get_new_conversation(self):
        self.add_app_permission(u'go.apps.bulk_message')
        response = self.client.get(reverse('conversations:new_conversation'))
        self.assertContains(response, 'Conversation name')
        self.assertContains(response, 'kind of conversation')
        self.assertContains(response, 'bulk_message')
        self.assertNotContains(response, 'survey')

    def test_post_new_conversation(self):
        self.add_app_permission(u'go.apps.bulk_message')
        conv_data = {
            'name': 'new conv',
            'conversation_type': 'bulk_message',
        }
        response = self.client.post(reverse('conversations:new_conversation'),
                                    conv_data)
        [conv] = self.user_api.active_conversations()
        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        self.assertEqual(conv.name, 'new conv')
        self.assertEqual(conv.conversation_type, 'bulk_message')

    def test_edit_conversation_details(self):
        conv = self.create_conversation(conversation_type=u'bulk_message',
                                        name=u'test', description=u'test')

        response = self.client.post(
            reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': 'edit_detail/',
            }), {
                'name': 'foo',
                'description': 'bar',
            })
        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        reloaded_conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertEqual(reloaded_conv.name, 'foo')
        self.assertEqual(reloaded_conv.description, 'bar')

    def test_conversation_contact_group_listing(self):
        conv = self.create_conversation(conversation_type=u'bulk_message',
                                        name=u'test', description=u'test')
        group1 = self.user_api.contact_store.new_group(u'Contact Group 1')
        group2 = self.user_api.contact_store.new_group(u'Contact Group 2')

        conv.add_group(group1)
        conv.save()

        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})

        resp = self.client.get(show_url)
        self.assertContains(resp, 'Contact Group 1')
        self.assertNotContains(resp, 'Contact Group 2')

    def test_conversation_contact_group_assignment(self):
        conv = self.create_conversation(conversation_type=u'bulk_message',
                                        name=u'test', description=u'test')
        group1 = self.user_api.contact_store.new_group(u'Contact Group 1')
        group2 = self.user_api.contact_store.new_group(u'Contact Group 2')

        groups_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': 'edit_groups/'})

        resp = self.client.post(groups_url, {
            'group': [group2.key]
        })

        self.assertEqual(resp.status_code, 302)

        reloaded_conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertFalse(group1.key in reloaded_conv.groups.keys())
        self.assertTrue(group2.key in reloaded_conv.groups.keys())

    def test_post_new_conversation_extra_endpoints(self):
        self.add_app_permission(u'go.apps.wikipedia')
        conv_data = {
            'name': 'new conv',
            'conversation_type': 'wikipedia',
        }
        response = self.client.post(reverse('conversations:new_conversation'),
                                    conv_data)
        [conv] = self.user_api.active_conversations()
        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        self.assertEqual(conv.name, 'new conv')
        self.assertEqual(conv.conversation_type, 'wikipedia')
        self.assertEqual(list(conv.extra_endpoints), [u'sms_content'])

    def test_index(self):
        """Display all conversations"""
        response = self.client.get(reverse('conversations:index'))
        self.assertNotContains(response, u'My Conversation')

        self.create_conversation(
            name=u'My Conversation', conversation_type=u'bulk_message')
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, u'My Conversation')

    def test_index_search(self):
        """Filter conversations based on query string"""
        conv = self.create_conversation(conversation_type=u'bulk_message')

        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, conv.name)

        response = self.client.get(reverse('conversations:index'), {
            'query': 'something that does not exist in the fixtures'})
        self.assertNotContains(response, conv.name)

    def test_index_search_on_type(self):
        conv = self.create_conversation(conversation_type=u'bulk_message')
        self.add_app_permission(u'go.apps.surveys')
        self.add_app_permission(u'go.apps.bulk_message')

        def search(conversation_type):
            return self.client.get(reverse('conversations:index'), {
                'query': conv.name,
                'conversation_type': conversation_type,
            })

        self.assertContains(search('bulk_message'), conv.key)
        self.assertNotContains(search('survey'), conv.key)

    def test_index_search_on_status(self):
        conv = self.create_conversation(conversation_type=u'bulk_message')

        def search(conversation_status):
            return self.client.get(reverse('conversations:index'), {
                'query': conv.name,
                'conversation_status': conversation_status,
            })

        # it should be draft
        self.assertContains(search('draft'), conv.key)
        self.assertNotContains(search('running'), conv.key)
        self.assertNotContains(search('finished'), conv.key)

        # now it should be running
        conv.start()
        # Set the status manually, because it's in `starting', not `running'
        conv = self.user_api.get_wrapped_conversation(conv.key)
        conv.set_status_started()
        conv.save()
        self.assertNotContains(search('draft'), conv.key)
        self.assertContains(search('running'), conv.key)
        self.assertNotContains(search('finished'), conv.key)

        # now it shouldn't be
        conv.end_conversation()
        self.assertNotContains(search('draft'), conv.key)
        self.assertNotContains(search('running'), conv.key)
        self.assertContains(search('finished'), conv.key)

    @skip("Update this for new lifecycle.")
    def test_received_messages(self):
        """
        Test received_messages helper function
        """
        conversation = self.get_wrapped_conv()
        conversation.old_start()
        contacts = []
        for bunch in conversation.get_opted_in_contact_bunches(
                conversation.delivery_class):
            contacts.extend(bunch)
        [contact] = contacts
        [batch] = conversation.get_batches()
        self.assertEqual(conversation.received_messages(), [])
        [tag] = self.api.batch_tags(batch.key)
        to_addr = "+123" + tag[1][-5:]

        # TODO: Decide what we want here.
        #       We get 'contact=None', but everything else is there
        # unknown contact
        # msg = self.mkmsg_in('hello', to_addr=to_addr)
        # self.api.mdb.add_inbound_message(msg, tag=tag)
        # self.assertEqual(conversation.replies(), [])

        # TODO: Actually put the contact in here.
        # known contact
        msg = self.mkmsg_in('hello', to_addr=to_addr,
                            from_addr=contact.msisdn.lstrip('+'))
        self.api.mdb.add_inbound_message(msg, tag=tag)
        [reply_msg] = conversation.received_messages()
        self.assertTrue(reply_msg, msg)

    def test_end_conversation(self):
        """
        Test the end_conversation helper function
        """
        conv = self.create_conversation(conversation_type=u'bulk_message')
        self.assertFalse(conv.ended())
        conv.end_conversation()
        self.assertTrue(conv.ended())

    @skip("Update this for new lifecycle.")
    def test_tag_releasing(self):
        """
        Test that tags are released when a conversation is ended.
        """
        conversation = self.get_wrapped_conv()
        conversation.old_start()
        [message_batch] = conversation.get_batches()
        self.assertEqual(len(conversation.get_tags()), 1)
        conversation.end_conversation()
        [msg_tag] = self.api.batch_tags(message_batch.key)
        tag_batch = lambda t: self.api.mdb.get_tag_info(t).current_batch.key
        self.assertEqual(tag_batch(msg_tag), None)

    def test_pagination(self):
        for i in range(13):
            conv = self.create_conversation(conversation_type=u'bulk_message')
        response = self.client.get(reverse('conversations:index'))
        # CONVERSATIONS_PER_PAGE = 12
        self.assertContains(response, conv.name, count=12)
        response = self.client.get(reverse('conversations:index'), {'p': 2})
        self.assertContains(response, conv.name, count=1)

    def test_pagination_with_query_and_type(self):
        self.add_app_permission(u'go.apps.surveys')
        self.add_app_permission(u'go.apps.bulk_message')
        for i in range(13):
            conv = self.create_conversation(conversation_type=u'bulk_message')
        response = self.client.get(reverse('conversations:index'), {
            'query': conv.name,
            'p': 2,
            'conversation_type': 'bulk_message',
            'conversation_status': 'draft',
        })

        self.assertNotContains(response, '?p=2')

    def test_scrub_tokens(self):
        content = 'Please visit http://example.com/t/6be226/ ' \
                  'to start your conversation.'
        expected = 'Please visit http://example.com/t/******/ ' \
                   'to start your conversation.'
        self.assertEqual(scrub_tokens(content), expected)
        self.assertEqual(scrub_tokens(content * 2), expected * 2)
