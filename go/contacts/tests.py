from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse


class ContactsTestCase(TestCase):

    fixtures = ['test_user']

    def setUp(self):
        self.client = Client()
        self.client.login(username='username', password='password')

    def tearDown(self):
        pass

    def test_redirect_index(self):
        response = self.client.get(reverse('contacts:index'))
        self.assertRedirects(response, reverse('contacts:groups'))
