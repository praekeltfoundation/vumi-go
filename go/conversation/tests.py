from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings
from go.conversation.models import Conversation
from go.base.models import ContactGroup, Contact
from datetime import datetime
from os import path


def reload_record(record):
    return record.__class__.objects.get(pk=record.pk)


class ConversationTestCase(TestCase):

    fixtures = ['test_user']

    def setUp(self):
        self.client = Client()
        self.client.login(username='username', password='password')

    def tearDown(self):
        pass

    def test_new_conversation(self):
        """test the creationg of a new conversation"""
        # render the form
        self.assertFalse(Conversation.objects.exists())
        response = self.client.get(reverse('conversation:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('conversation:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
        })
        self.assertTrue(Conversation.objects.exists())


class ContactGroupForm(TestCase):

    fixtures = ['test_user', 'test_conversation', 'test_group']

    def setUp(self):
        self.user = User.objects.get(username='username')
        self.conversation = self.user.conversation_set.latest()
        self.client = Client()
        self.client.login(username=self.user.username, password='password')
        self.csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'))

    def tearDown(self):
        pass

    def test_group_creation(self):
        """test creation of a new contact group when starting a conversation"""
        self.assertEqual(ContactGroup.objects.count(), 1)
        response = self.client.post(reverse('conversation:participants',
            kwargs={'conversation_pk': self.conversation.pk}))
        self.assertEqual(ContactGroup.objects.count(), 1)
        response = self.client.post(reverse('conversation:participants',
            kwargs={'conversation_pk': self.conversation.pk}), {
                'name': 'Test Group'
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactGroup.objects.count(), 2)
        self.assertEqual(ContactGroup.objects.latest().name, 'Test Group')

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        response = self.client.post(reverse('conversation:participants',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'groups': [grp.pk for grp in ContactGroup.objects.all()]
        })
        self.assertRedirects(response, reverse('conversation:send', kwargs={
            'conversation_pk': self.conversation.pk}))

    def test_contacts_upload(self):
        """test uploading of contacts via CSV file"""
        response = self.client.post(reverse('conversation:participants',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'name': 'Test Group',
            'file': self.csv_file,
        })
        self.assertRedirects(response, reverse('conversation:send',
            kwargs={'conversation_pk': self.conversation.pk}))
        group = ContactGroup.objects.latest()
        self.assertEquals(group.name, 'Test Group')
        self.assertEquals(Contact.objects.count(), 3)
        for idx, contact in enumerate(Contact.objects.all(), start=1):
            self.assertTrue(contact.name, 'Name %s' % idx)
            self.assertTrue(contact.surname, 'Surname %s' % idx)
            self.assertTrue(contact.msisdn.startswith('+2776123456%s' % idx))
            self.assertIn(contact, group.contact_set.all())
        self.assertIn(group, self.conversation.groups.all())

    def test_priority_of_select_over_group_creation(self):
        """Selected existing groups takes priority over creating
        new groups"""
        group = ContactGroup.objects.create(user=self.user, name='Test Group')
        response = self.client.post(reverse('conversation:participants',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'name': 'Should be ignored',
            'contact_group': group.pk,
            'file': self.csv_file,
        })
        self.assertRedirects(response, reverse('conversation:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        self.assertEqual(ContactGroup.objects.latest(), group)
        self.assertEqual(ContactGroup.objects.count(), 2)
        self.assertEqual(Contact.objects.count(), 3)
        for contact in Contact.objects.all():
            self.assertIn(contact, group.contact_set.all())
        self.assertIn(group, self.conversation.groups.all())

    def test_sending_preview(self):
        """test sending of conversation to a selected set of preview
        contacts"""
        response = self.client.post(reverse('conversation:send', kwargs={
            'conversation_pk': self.conversation.pk
        }), {
            'contact': [c.pk for c in Contact.objects.all()]
        })
