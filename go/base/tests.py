from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User, Permission
from django import template
from go.base.templatetags import go_tags
from go.base import utils
import string


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


class FakeTemplateToken(object):
    def __init__(self, contents):
        self.contents = contents


class GoTemplateTagsTestCase(TestCase):
    
    def test_load_alphabet(self):
        
        token = FakeTemplateToken('load_alphabet as alphabet')
        node = go_tags.load_alphabet('bogus', token)
        context = {}
        output = node.render(context)
        self.assertEqual(output, '')
        self.assertEqual(node.var_name, 'alphabet')
        self.assertEqual(context['alphabet'], string.ascii_lowercase)
    
    def test_load_alphabet_value_error(self):
        self.assertRaises(template.TemplateSyntaxError, go_tags.load_alphabet, 
            'bogus', FakeTemplateToken('load_alphabet'))
        self.assertRaises(template.TemplateSyntaxError, go_tags.load_alphabet, 
            'bogus', FakeTemplateToken('load_alphabet as'))

class UtilsTestCase(TestCase):
    
    fixtures = ['test_user']
    
    def test_padded_queryset(self):
        short_list = User.objects.all()[:1]
        padded_list = utils.padded_queryset(short_list)
        expected_list = list(short_list) + [None, None, None, None, None]
        self.assertEqual(padded_list, expected_list)
    
    def test_padded_queryset_limiting(self):
        long_list = Permission.objects.all()
        self.assertTrue(long_list.count() > 6)
        padded_list = utils.padded_queryset(long_list)
        self.assertEqual(len(padded_list), 6)