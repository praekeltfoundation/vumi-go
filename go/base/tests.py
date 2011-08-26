from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User


class AuthenticationTestCase(TestCase):
    
    def setUp(self):
        self.username = 'username'
        self.password = 'password'
        self.first_name = 'Test'
        self.last_name = 'User'
        self.user = User.objects.create_superuser(self.username, 
            '%s@domain.com' % self.username, self.password)
        self.user.first_name = self.first_name
        self.user.last_name = self.last_name
        self.user.save()
        self.client = Client()
    
    def tearDown(self):
        pass
    
    def test_redirect_to_login(self):
        """test the authentication mechanism"""
        response = self.client.get(reverse('go:home'))
        self.assertRedirects(response, '/accounts/login/?next=/')
    
    def test_login(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('go:home'))
        self.assertContains(response, '%s %s' % (self.first_name, self.last_name))
    
    def test_logged_out(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('logout'))
        response = self.client.get(reverse('go:home'))
        self.assertRedirects(response, '/accounts/login/?next=/')