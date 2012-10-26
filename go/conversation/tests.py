from os import path
from datetime import datetime

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.conf import settings

from go.vumitools.api import VumiApi
from go.vumitools.tests.utils import CeleryTestMixIn
from go.base.tests.utils import VumiGoDjangoTestCase, declare_longcode_tags
from go.base.utils import vumi_api_for_user
from vumi.message import TransportUserMessage


TEST_GROUP_NAME = u"Test Group"
TEST_CONTACT_NAME = u"Name"
TEST_CONTACT_SURNAME = u"Surname"
TEST_SUBJECT = u"Test Conversation"


def newest(models):
    return max(models, key=lambda m: m.created_at)


class ConversationTestCase(VumiGoDjangoTestCase, CeleryTestMixIn):

    fixtures = ['test_user']

    def setUp(self):
        super(ConversationTestCase, self).setUp()
        self.setup_api()
        self.declare_longcode_tags()
        self.setup_celery_for_tests()
        self.setup_riak_fixtures()

        # self.conversation = self.user.conversation_set.latest()
        self.client = Client()
        self.client.login(username=self.user.username, password='password')
        self.csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'))

    def setup_riak_fixtures(self):
        self.user = self.mk_django_user()
        self.user_api = vumi_api_for_user(self.user)
        self._persist_riak_managers.append(self.user_api.api.manager)
        self.contact_store = self.user_api.contact_store
        self.contact_store.contacts.enable_search()
        self.conv_store = self.user_api.conversation_store

        # We need a group
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        self.group_key = group.key

        # Also a contact
        contact = self.contact_store.new_contact(
            name=TEST_CONTACT_NAME, surname=TEST_CONTACT_SURNAME,
            msisdn=u"+27761234567")
        contact.add_to_group(group)
        contact.save()
        self.contact_key = contact.key

        # And a conversation
        conversation = self.conv_store.new_conversation(
            conversation_type=u'bulk_message', subject=TEST_SUBJECT,
            message=u"Test message", delivery_class=u"sms",
            delivery_tag_pool=u"longcode", groups=[self.group_key])
        self.conv_key = conversation.key

    def tearDown(self):
        self.restore_celery()
        super(ConversationTestCase, self).tearDown()

    def mkmsg_in(self, content, **kw):
        kw.setdefault('to_addr', '+123')
        kw.setdefault('from_addr', '+456')
        kw.setdefault('transport_name', 'dummy_transport')
        kw.setdefault('transport_type', 'sms')
        return TransportUserMessage(content=content, **kw)

    def setup_api(self):
        self.api = VumiApi.from_config(settings.VUMI_API_CONFIG)

    def declare_longcode_tags(self):
        declare_longcode_tags(self.api)

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def test_index(self):
        """Display all conversations"""
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, self.get_wrapped_conv().subject)

    def test_index_search(self):
        """Filter conversations based on query string"""
        response = self.client.get(reverse('conversations:index'), {
            'query': 'something that does not exist in the fixtures'})
        self.assertNotContains(response, TEST_SUBJECT)

    def test_index_search_on_type(self):
        conversation = self.get_wrapped_conv()
        conversation.c.conversation_type = u'survey'
        conversation.save()

        def search(conversation_type):
            return self.client.get(reverse('conversations:index'), {
                'query': TEST_SUBJECT,
                'conversation_type': conversation_type,
                })

        self.assertNotContains(search('bulk_message'), conversation.message)
        self.assertContains(search('survey'), conversation.message)

    def test_index_search_on_status(self):
        conversation = self.get_wrapped_conv()

        def search(conversation_status):
            return self.client.get(reverse('conversations:index'), {
                'query': conversation.subject,
                'conversation_status': conversation_status,
                })

        # it should be draft
        self.assertContains(search('draft'), conversation.message)
        self.assertNotContains(search('running'), conversation.message)
        self.assertNotContains(search('finished'), conversation.message)

        # now it should be running
        conversation.start()
        self.assertNotContains(search('draft'), conversation.message)
        self.assertContains(search('running'), conversation.message)
        self.assertNotContains(search('finished'), conversation.message)

        # now it shouldn't be
        conversation.end_conversation()
        self.assertNotContains(search('draft'), conversation.message)
        self.assertNotContains(search('running'), conversation.message)
        self.assertContains(search('finished'), conversation.message)

    def test_replies(self):
        """
        Test replies helper function
        """
        conversation = self.get_wrapped_conv()
        [contact] = conversation.get_opted_in_contacts()
        self.assertEqual(conversation.replies(), [])
        conversation.start()
        [batch] = conversation.get_batches()
        self.assertEqual(conversation.replies(), [])
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
        [reply] = conversation.replies()
        self.assertTrue(isinstance(reply.pop('time'), datetime))
        self.assertEqual(reply.pop('contact').key, contact.key)
        self.assertEqual(reply, {
            'content': u'hello',
            'source': 'Long code',
            'type': u'sms',
            })

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
        # start with a clean state
        for conv in self.conv_store.list_conversations():
            # TODO: Better way to delete these.
            conv._riak_object.delete()

        # Create 10
        for i in range(10):
            self.conv_store.new_conversation(
                conversation_type=u'bulk_message', subject=TEST_SUBJECT,
                message=u"", delivery_class=u"sms",
                delivery_tag_pool=u"longcode")
        response = self.client.get(reverse('conversations:index'))
        # CONVERSATIONS_PER_PAGE = 6
        self.assertContains(response, TEST_SUBJECT, count=6)
        response = self.client.get(reverse('conversations:index'), {'p': 2})
        self.assertContains(response, TEST_SUBJECT, count=4)
