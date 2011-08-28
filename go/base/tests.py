from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings
from go.base.models import ContactGroup, Contact
from os import path
import tempfile
import csv

def reload_record(record):
    return record.__class__.objects.get(pk=record.pk)

class AuthenticationTestCase(TestCase):
    
    fixtures = ['test_user']
    
    def setUp(self):
        self.user = User.objects.get(username='username')
        self.client = Client()
    
    def tearDown(self):
        pass
    
    def test_redirect_to_login(self):
        """test the authentication mechanism"""
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, '%s?next=/' % reverse('login'))
    
    def test_login(self):
        """test correct login"""
        self.client.login(username=self.user.username, password='password')
        response = self.client.get(reverse('home'))
        self.assertContains(response, '%s %s' % (self.user.first_name, 
            self.user.last_name))
    
    def test_logged_out(self):
        """test logout & redirect after logout"""
        self.client.login(username=self.user.username, password='password')
        response = self.client.get(reverse('logout'))
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, '%s?next=/' % reverse('login'))
    
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
        response = self.client.post(reverse('conversation:participants', kwargs={
            'conversation_pk': self.conversation.pk}))
        self.assertEqual(ContactGroup.objects.count(), 1)
        response = self.client.post(reverse('conversation:participants', kwargs={
            'conversation_pk': self.conversation.pk}), {
            'name': 'Test Group'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactGroup.objects.count(), 2)
        self.assertEqual(ContactGroup.objects.latest().name, 'Test Group')
    
    def test_contacts_upload(self):
        """test uploading of contacts via CSV file"""
        response = self.client.post(reverse('conversation:participants', kwargs={
            'conversation_pk': self.conversation.pk}), {
            'name': 'Test Group',
            'file': self.csv_file,
        })
        self.assertRedirects(response, reverse('conversation:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        group = ContactGroup.objects.latest()
        self.assertEquals(group.name, 'Test Group')
        self.assertEquals(Contact.objects.count(), 3)
        for idx, contact in enumerate(Contact.objects.all(), start=1):
            self.assertTrue(contact.name, 'Name %s' % idx)
            self.assertTrue(contact.surname, 'Surname %s' % idx)
            self.assertTrue(contact.msisdn.startswith('+2776123456%s' % idx))
            self.assertIn(contact, group.contact_set.all())
        self.assertEqual(reload_record(self.conversation).group, group)
        
    def test_priority_of_select_over_group_creation(self):
        """Selected existing groups takes priority over creating
        new groups"""
        group = ContactGroup.objects.create(user=self.user, name='Test Group')
        response = self.client.post(reverse('conversation:participants', kwargs={
            'conversation_pk': self.conversation.pk}), {
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
        self.assertEqual(reload_record(self.conversation).group, group)
        
    
    def test_sending_preview(self):
        """test sending of conversation to a selected set of preview contacts"""
        response = self.client.post(reverse('conversation:send', kwargs={
            'conversation_pk': self.conversation.pk
        }), {
            'contact': [c.pk for c in Contact.objects.all()]
        })
