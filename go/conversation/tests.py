from os import path
from datetime import datetime

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.conf import settings

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.conversation.templatetags.conversation_tags import scrub_tokens


def newest(models):
    return max(models, key=lambda m: m.created_at)


class ConversationTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(ConversationTestCase, self).setUp()
        self.setup_riak_fixtures()

        # self.conversation = self.user.conversation_set.latest()
        self.client = Client()
        self.client.login(username=self.user.username, password='password')
        self.csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'))

    def get_wrapped_conv(self):
        return self.user_api.get_wrapped_conversation(self.conv_key)

    def test_index(self):
        """Display all conversations"""
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, self.get_wrapped_conv().name)

    def test_index_search(self):
        """Filter conversations based on query string"""
        response = self.client.get(reverse('conversations:index'), {
            'query': 'something that does not exist in the fixtures'})
        self.assertNotContains(response, self.TEST_CONVERSATION_NAME)

    def test_index_search_on_type(self):
        conversation = self.get_wrapped_conv()
        conversation.c.conversation_type = u'survey'
        conversation.save()

        def search(conversation_type):
            return self.client.get(reverse('conversations:index'), {
                'query': self.TEST_CONVERSATION_NAME,
                'conversation_type': conversation_type,
                })

        self.assertNotContains(
            search('bulk_message'), conversation.config['content'])
        self.assertContains(search('survey'), conversation.config['content'])

    def test_index_search_on_status(self):
        conversation = self.get_wrapped_conv()

        def search(conversation_status):
            return self.client.get(reverse('conversations:index'), {
                'query': conversation.name,
                'conversation_status': conversation_status,
                })

        # it should be draft
        self.assertContains(search('draft'), conversation.config['content'])
        self.assertNotContains(
            search('running'), conversation.config['content'])
        self.assertNotContains(
            search('finished'), conversation.config['content'])

        # now it should be running
        conversation.start()
        self.assertNotContains(search('draft'), conversation.config['content'])
        self.assertContains(search('running'), conversation.config['content'])
        self.assertNotContains(
            search('finished'), conversation.config['content'])

        # now it shouldn't be
        conversation.end_conversation()
        self.assertNotContains(search('draft'), conversation.config['content'])
        self.assertNotContains(
            search('running'), conversation.config['content'])
        self.assertContains(search('finished'), conversation.config['content'])

    def test_received_messages(self):
        """
        Test received_messages helper function
        """
        conversation = self.get_wrapped_conv()
        conversation.start()
        contacts = []
        for bunch in conversation.get_opted_in_contact_bunches():
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
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.ended())
        conversation.end_conversation()
        self.assertTrue(conversation.ended())

    def test_tag_releasing(self):
        """
        Test that tags are released when a conversation is ended.
        """
        conversation = self.get_wrapped_conv()
        conversation.start()
        [message_batch] = conversation.get_batches()
        self.assertEqual(len(conversation.get_tags()), 1)
        conversation.end_conversation()
        [msg_tag] = self.api.batch_tags(message_batch.key)
        tag_batch = lambda t: self.api.mdb.get_tag_info(t).current_batch.key
        self.assertEqual(tag_batch(msg_tag), None)

    def test_pagination(self):
        # Create 9, we already have 1 from setUp()
        for i in range(9):
            self.conv_store.new_conversation(
                conversation_type=u'bulk_message',
                name=self.TEST_CONVERSATION_NAME, config={u'content': u""},
                delivery_class=u"sms", delivery_tag_pool=u"longcode")
        response = self.client.get(reverse('conversations:index'))
        # CONVERSATIONS_PER_PAGE = 6
        self.assertContains(response, self.TEST_CONVERSATION_NAME, count=6)
        response = self.client.get(reverse('conversations:index'), {'p': 2})
        self.assertContains(response, self.TEST_CONVERSATION_NAME, count=4)

    def test_scrub_tokens(self):
        content = 'Please visit http://example.com/t/6be226/ ' \
                    'to start your conversation.'
        expected = 'Please visit http://example.com/t/******/ ' \
                    'to start your conversation.'
        self.assertEqual(scrub_tokens(content), expected)
        self.assertEqual(scrub_tokens(content * 2), expected * 2)
