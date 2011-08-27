from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User


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