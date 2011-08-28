from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings
from go.base.models import ContactGroup, Contact
from os import path
import tempfile
import csv

class AuthenticationTestCase(TestCase):
    
    fixtures = ['test_user.json']
    
    def setUp(self):
        self.user = User.objects.get(username='username')
        self.client = Client()
    
    def tearDown(self):
        pass
    
    def test_redirect_to_login(self):
        """test the authentication mechanism"""
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, '/accounts/login/?next=/')
    
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
        self.assertRedirects(response, '/accounts/login/?next=/')
    
class ContactGroupForm(TestCase):
    
    fixtures = ['test_user', 'test_conversation']
    
    def setUp(self):
        self.user = User.objects.get(username='username')
        self.conversation = self.user.conversation_set.latest()
        self.client = Client()
        self.client.login(username=self.user.username, password='password')
    
    def tearDown(self):
        pass
    
    def test_group_creation(self):
        """test creation of a new contact group when starting a conversation"""
        self.assertFalse(ContactGroup.objects.exists())
        response = self.client.post(reverse('conversation:participants', kwargs={
            'conversation_pk': self.conversation.pk}))
        self.assertFalse(ContactGroup.objects.exists())
        response = self.client.post(reverse('conversation:participants', kwargs={
            'conversation_pk': self.conversation.pk}), {
            'name': 'Test Group'
        })
        self.assertEquals(ContactGroup.objects.latest().name, 'Test Group')
    
    def test_contacts_upload(self):
        """test uploading of contacts via CSV file"""
        response = self.client.post(reverse('conversation:participants', kwargs={
            'conversation_pk': self.conversation.pk}), {
            'name': 'Test Group',
            'file': open(path.join(settings.PROJECT_ROOT, 'base', 'fixtures', 
                'sample-contacts.csv')),
        })
        
        group = ContactGroup.objects.latest()
        self.assertEquals(group.name, 'Test Group')
        self.assertEquals(Contact.objects.count(), 3)
        for contact in Contact.objects.all():
            self.assertIn(contact, group.contact_set.all())
    