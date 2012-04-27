from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings
from go.conversation.models import Conversation
from go.conversation.views import CONVERSATIONS_PER_PAGE
from go.contacts.models import ContactGroup, Contact
from go.base.utils import padded_queryset
from vumi.tests.utils import FakeRedis
from vumi.message import TransportUserMessage
from go.vumitools.tests.utils import CeleryTestMixIn, VumiApiCommand
from datetime import datetime
from os import path


def reload_record(record):
    return record.__class__.objects.get(pk=record.pk)


class ConversationTestCase(TestCase):

    fixtures = ['test_user', 'test_conversation']

    def setUp(self):
        self.client = Client()
        self.client.login(username='username', password='password')

    def tearDown(self):
        pass

    def test_recent_conversations(self):
        """
        Conversation.objects.recent() should return the most recent
        conversations, if given a limit it should return a list of that
        exact size padded with the value of `padding`.
        """
        conversations = padded_queryset(Conversation.objects.all(), size=10,
            padding='')
        self.assertEqual(len(conversations), 10)
        self.assertEqual(len(filter(lambda v: v is not '', conversations)), 1)


class ContactGroupForm(TestCase, CeleryTestMixIn):

    fixtures = ['test_user', 'test_conversation', 'test_group', 'test_contact']

    def setUp(self):
        self.setup_api()
        self.declare_longcode_tags()
        self.setup_celery_for_tests()
        self.user = User.objects.get(username='username')
        self.conversation = self.user.conversation_set.latest()
        self.client = Client()
        self.client.login(username=self.user.username, password='password')
        self.csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'))

    def tearDown(self):
        self.restore_celery()

    def setup_api(self):
        self._fake_redis = FakeRedis()
        self._old_vumi_api_config = settings.VUMI_API_CONFIG
        settings.VUMI_API_CONFIG = {
            'redis_cls': lambda **kws: self._fake_redis,
            'message_store': {},
            'message_sender': {},
            }

    def teardown_api(self):
        settings.VUMI_API_CONFIG = self._old_vumi_api_config
        self._fake_redis.teardown()

    def declare_longcode_tags(self):
        api = Conversation.vumi_api()
        api.declare_tags([("longcode", "default%s" % i) for i
                          in range(10001, 10001 + 4)])

    def test_index(self):
        """Display all conversations"""
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, self.conversation.subject)

    def test_index_search(self):
        """Filter conversations based on query string"""
        response = self.client.get(reverse('conversations:index'), {
            'query': 'something that does not exist in the fixtures'})
        self.assertNotContains(response, self.conversation.subject)

    def test_index_search_on_type(self):
        self.conversation.conversation_type = 'survey'
        self.conversation.save()

        def search(conversation_type):
            return self.client.get(reverse('conversations:index'), {
                'query': self.conversation.subject,
                'conversation_type': conversation_type,
                })

        self.assertNotContains(search('bulk_message'),
                self.conversation.message)
        self.assertContains(search('survey'),
                self.conversation.message)

    def test_index_search_on_status(self):

        def search(conversation_status):
            return self.client.get(reverse('conversations:index'), {
                'query': self.conversation.subject,
                'conversation_status': conversation_status,
                })

        # it should be draft
        self.assertContains(search('draft'),
                self.conversation.message)
        self.assertNotContains(search('running'),
                self.conversation.message)
        self.assertNotContains(search('finished'),
                self.conversation.message)

        # now it should be running
        self.conversation.start()
        self.assertNotContains(search('draft'),
                self.conversation.message)
        self.assertContains(search('running'),
                self.conversation.message)
        self.assertNotContains(search('finished'),
                self.conversation.message)

        # now it shouldn't be
        self.conversation.end_conversation()
        self.assertNotContains(search('draft'),
                self.conversation.message)
        self.assertNotContains(search('running'),
                self.conversation.message)
        self.assertContains(search('finished'),
                self.conversation.message)

    def test_replies(self):
        """
        Test replies helper function
        """
        vumiapi = Conversation.vumi_api()
        [contact] = self.conversation.people()
        self.assertEqual(self.conversation.replies(), [])
        self.conversation.start()
        [batch] = self.conversation.message_batch_set.all()
        self.assertEqual(self.conversation.replies(), [])
        [tag] = vumiapi.batch_tags(batch.batch_id)
        to_addr = "+123" + tag[1][-5:]

        # unknown contact
        msg = self.mkmsg_in('hello', to_addr=to_addr)
        vumiapi.mdb.add_inbound_message(msg, tag=tag)
        self.assertEqual(self.conversation.replies(), [])

        # known contact
        msg = self.mkmsg_in('hello', to_addr=to_addr,
                            from_addr=contact.msisdn.lstrip('+'))
        vumiapi.mdb.add_inbound_message(msg, tag=tag)
        [reply] = self.conversation.replies()
        self.assertTrue(isinstance(reply.pop('time'), datetime))
        self.assertEqual(reply, {
            'contact': contact,
            'content': u'hello',
            'source': 'Long code',
            'type': u'sms',
            })

    def test_end_conversation(self):
        """
        Test the end_conversation helper function
        """
        self.assertFalse(self.conversation.ended())
        self.conversation.end_conversation()
        self.assertTrue(self.conversation.ended())

    def test_tag_releasing(self):
        """
        Test that tags are released when a conversation is ended.
        """
        vumiapi = Conversation.vumi_api()
        self.conversation.start()
        [message_batch] = self.conversation.message_batch_set.all()
        self.assertEqual(len(vumiapi.batch_tags(message_batch.batch_id)), 1)
        self.conversation.end_conversation()
        [msg_tag] = vumiapi.batch_tags(message_batch.batch_id)
        self.assertEqual(vumiapi.mdb.tag_common(msg_tag)['current_batch_id'],
                         None)

    def test_pagination(self):
        # start with a clean state
        Conversation.objects.all().delete()
        # Create 10
        for i in range(10):
            Conversation.objects.create(user=self.user,
                subject='Test Conversation', message='',
                start_date=datetime.now().date(),
                start_time=datetime.now().time())
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, 'Test Conversation',
            count=CONVERSATIONS_PER_PAGE)
        response = self.client.get(reverse('conversations:index'), {
            'p': 2})
        self.assertContains(response, 'Test Conversation',
            count=4)
