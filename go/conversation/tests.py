from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings
from go.conversation.models import Conversation
from go.contacts.models import ContactGroup, Contact
from go.base.utils import padded_queryset
from vumi.tests.utils import FakeRedis
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

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        # render the form
        self.assertEqual(Conversation.objects.count(), 1)
        response = self.client.get(reverse('conversations:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('conversations:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
        })
        self.assertEqual(Conversation.objects.count(), 2)


class ContactGroupForm(TestCase, CeleryTestMixIn):

    fixtures = ['test_user', 'test_conversation', 'test_group', 'test_contact']

    def setUp(self):
        self.setup_api()
        self.declare_ambient_tags()
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
            'message_store': {
                'redis_cls': lambda **kws: self._fake_redis,
                },
            'message_sender': {},
            }

    def teardown_api(self):
        settings.VUMI_API_CONFIG = self._old_vumi_api_config
        self._fake_redis.teardown()

    def declare_ambient_tags(self):
        api = Conversation.vumi_api()
        api.declare_tags("ambient", ["default%s" % i for i
                                     in range(10001, 10001 + 4)])

    def acquire_all_ambient_tags(self):
        api = Conversation.vumi_api()
        for _i in range(4):
            api.acquire_tag("ambient")

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        response = self.client.post(reverse('conversations:people',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'groups': [grp.pk for grp in ContactGroup.objects.all()]
        })
        self.assertRedirects(response, reverse('conversations:send', kwargs={
            'conversation_pk': self.conversation.pk}))

    def test_index(self):
        """Display all conversations"""
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, self.conversation.subject)

    def test_index_search(self):
        """Filter conversations based on query string"""
        response = self.client.get(reverse('conversations:index'), {
            'q': 'something that does not exist in the fixtures'})
        self.assertNotContains(response, self.conversation.subject)

    def test_contacts_upload(self):
        """test uploading of contacts via CSV file"""
        self.assertEqual(ContactGroup.objects.count(), 1)
        response = self.client.post(reverse('conversations:upload',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'name': 'Unit Test Group',
            'file': self.csv_file,
        })
        self.assertRedirects(response, reverse('conversations:send',
            kwargs={'conversation_pk': self.conversation.pk}))
        group = ContactGroup.objects.latest()
        self.assertEqual(ContactGroup.objects.count(), 2)
        self.assertEqual(group.name, 'Unit Test Group')
        contacts = Contact.objects.filter(groups=group)
        self.assertEquals(contacts.count(), 3)
        for idx, contact in enumerate(contacts, start=1):
            self.assertTrue(contact.name, 'Name %s' % idx)
            self.assertTrue(contact.surname, 'Surname %s' % idx)
            self.assertTrue(contact.msisdn.startswith('+2776123456%s' % idx))
            self.assertIn(contact, group.contact_set.all())
        self.assertIn(group, self.conversation.groups.all())

    def test_contacts_upload_to_existing_group(self):
        """It should be able to upload new contacts to an existing group"""
        group = ContactGroup.objects.latest()
        group.contact_set.clear()
        response = self.client.post(reverse('conversations:upload',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'contact_group': group.pk,
            'file': self.csv_file,
        })
        self.assertRedirects(response, reverse('conversations:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        contacts = Contact.objects.filter(groups=group)
        self.assertEqual(contacts.count(), 3)
        self.assertIn(group, self.conversation.groups.all())

    def test_priority_of_name_over_select_group_creation(self):
        """Selected existing groups takes priority over creating
        new groups"""
        group = ContactGroup.objects.create(user=self.user, name='Test Group')
        response = self.client.post(reverse('conversations:upload',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'name': 'Name of Group',
            'contact_group': group.pk,
            'file': self.csv_file,
        })
        self.assertRedirects(response, reverse('conversations:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        new_group = ContactGroup.objects.latest()
        self.assertNotEqual(new_group, group)
        self.assertEqual(new_group.name, 'Name of Group')
        contacts = Contact.objects.filter(groups=new_group)
        self.assertEqual(contacts.count(), 3)
        self.assertIn(new_group, self.conversation.groups.all())

    def test_sending_preview(self):
        """test sending of conversation to a selected set of preview
        contacts"""
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('conversations:send', kwargs={
            'conversation_pk': self.conversation.pk,
        }), {
            'contact': [c.pk for c in Contact.objects.all()]
        })
        self.assertRedirects(response, reverse('conversations:start', kwargs={
            'conversation_pk': self.conversation.pk}))
        [cmd] = self.fetch_cmds(consumer)
        [batch] = self.conversation.preview_batch_set.all()
        [contact] = self.conversation.previewcontacts.all()
        msg_options = {"from_addr": "default10001"}
        self.assertEqual(cmd, VumiApiCommand.send(batch.batch_id,
                                                  "APPROVE? Test message",
                                                  msg_options,
                                                  contact.msisdn))

    def test_sending_preview_fails(self):
        """test failure to send previews"""
        self.acquire_all_ambient_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('conversations:send', kwargs={
            'conversation_pk': self.conversation.pk,
        }), {
            'contact': [c.pk for c in Contact.objects.all()]
        }, follow=True)
        self.assertRedirects(response, reverse('conversations:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        [] = self.fetch_cmds(consumer)
        [] = self.conversation.preview_batch_set.all()
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_start(self):
        """
        Test the start conversation view
        """
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('conversations:start', kwargs={
            'conversation_pk': self.conversation.pk}))
        self.assertRedirects(response, reverse('conversations:show', kwargs={
            'conversation_pk': self.conversation.pk}))

        [cmd] = self.fetch_cmds(consumer)
        [batch] = self.conversation.message_batch_set.all()
        [contact] = self.conversation.people()
        msg_options = {"from_addr": "default10001"}
        self.assertEqual(cmd, VumiApiCommand.send(batch.batch_id,
                                                  "Test message",
                                                  msg_options,
                                                  contact.msisdn))

    def test_start_fails(self):
        """
        Test failure to send messages
        """
        self.acquire_all_ambient_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('conversations:start', kwargs={
            'conversation_pk': self.conversation.pk}), follow=True)
        self.assertRedirects(response, reverse('conversations:start', kwargs={
            'conversation_pk': self.conversation.pk}))
        [] = self.fetch_cmds(consumer)
        [] = self.conversation.preview_batch_set.all()
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_preview_status(self):
        """
        Test preview status helper function
        """
        consumer = self.get_cmd_consumer()
        vumiapi = Conversation.vumi_api()
        [contact] = self.conversation.previewcontacts.all()
        self.assertEqual(self.conversation.preview_status(),
                         [(contact, 'waiting to send')])
        self.conversation.send_preview()
        [batch] = self.conversation.preview_batch_set.all()
        self.process_cmds(vumiapi.mdb, consumer=consumer)
        self.assertEqual(self.conversation.preview_status(),
                         [(contact, 'awaiting reply')])
        [tag] = vumiapi.mdb.batch_common(batch.batch_id)['tags']
        to_addr = "+123" + tag[-5:]

        # unknown contact
        msg = self.mkmsg_in('hello', to_addr=to_addr)
        vumiapi.mdb.add_inbound_message(msg)
        self.assertEqual(self.conversation.preview_status(),
                         [(contact, 'awaiting reply')])

        # known contact
        msg = self.mkmsg_in('approve', to_addr=to_addr,
                            from_addr=contact.msisdn.lstrip('+'))
        vumiapi.mdb.add_inbound_message(msg)
        self.assertEqual(self.conversation.preview_status(),
                         [(contact, 'approved')])

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('conversations:show', kwargs={
            'conversation_pk': self.conversation.pk}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.subject, 'Test Conversation')

    def test_replies(self):
        """
        Test replies helper function
        """
        consumer = self.get_cmd_consumer()
        vumiapi = Conversation.vumi_api()
        [contact] = self.conversation.people()
        self.assertEqual(self.conversation.replies(), [])
        self.conversation.send_messages()
        [batch] = self.conversation.message_batch_set.all()
        self.process_cmds(vumiapi.mdb, consumer=consumer)
        self.assertEqual(self.conversation.replies(), [])
        [tag] = vumiapi.mdb.batch_common(batch.batch_id)['tags']
        to_addr = "+123" + tag[-5:]

        # unknown contact
        msg = self.mkmsg_in('hello', to_addr=to_addr)
        vumiapi.mdb.add_inbound_message(msg)
        self.assertEqual(self.conversation.replies(), [])

        # known contact
        msg = self.mkmsg_in('hello', to_addr=to_addr,
                            from_addr=contact.msisdn.lstrip('+'))
        vumiapi.mdb.add_inbound_message(msg)
        [reply] = self.conversation.replies()
        self.assertTrue(isinstance(reply.pop('time'), datetime))
        self.assertEqual(reply, {
            'contact': contact,
            'content': u'hello',
            'source': 'SMS',
            'type': 'sms',
            })
