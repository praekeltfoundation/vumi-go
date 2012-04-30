# -*- coding: utf8 -*-
from os import path

from django.conf import settings
from django.test.client import Client
from django.core.urlresolvers import reverse

from go.base.models import User
from go.base.tests.utils import VumiGoDjangoTestCase
from go.vumitools.contact import ContactStore


TEST_GROUP_NAME = u"Test Group"
TEST_CONTACT_NAME = u"Name"
TEST_CONTACT_SURNAME = u"Surname"


class ContactsTestCase(VumiGoDjangoTestCase):

    fixtures = ['test_user']

    def setUp(self):
        super(ContactsTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

        self.group_url = reverse('contacts:group', kwargs={
                'group_name': TEST_GROUP_NAME})
        self.contact_url = reverse('contacts:person', kwargs={
                'person_key': self.contact_key})

    def setup_riak_fixtures(self):
        self.user = User.objects.get(username='username')
        self.contact_store = ContactStore.from_django_user(self.user)
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        contact = self.contact_store.new_contact(
            name=TEST_CONTACT_NAME, surname=TEST_CONTACT_SURNAME,
            msisdn=u"+27761234567")
        contact.add_to_group(group)
        contact.save()
        self.contact_key = contact.key

    def test_redirect_index(self):
        response = self.client.get(reverse('contacts:index'))
        self.assertRedirects(response, reverse('contacts:groups'))

    def test_groups_creation(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': 'a new group',
        })
        group = self.contact_store.get_group(u'a new group')
        self.assertNotEqual(group, None)
        self.assertRedirects(response, reverse('contacts:group', kwargs={
            'group_name': group.key,
        }))

    def test_groups_creation_with_funny_chars(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': 'a new group! with cüte chars\'s',
        })
        group = self.contact_store.get_group(u'a new group')
        self.assertNotEqual(group, None)
        self.assertRedirects(response, reverse('contacts:group', kwargs={
            'group_name': group.key,
        }))

    def test_group_contact_querying(self):
        # test no-match
        response = self.client.get(self.group_url, {
            'q': 'this should not match',
        })
        self.assertContains(response, 'No contact match')

        # test match name
        response = self.client.get(self.group_url, {
            'q': TEST_CONTACT_NAME,
        })
        self.assertContains(response, self.contact_url)

        # test match surname
        response = self.client.get(self.group_url, {
            'q': TEST_CONTACT_SURNAME,
        })
        self.assertContains(response, self.contact_url)

    def test_group_contact_filter_by_letter(self):
        first_letter = TEST_CONTACT_SURNAME[0]

        # Assert that our name doesn't start with our "fail" case.
        self.assertNotEqual(first_letter.lower(), 'z')

        response = self.client.get(self.group_url, {'l': 'z'})
        self.assertContains(response, 'No contact surnames start with '
                                        'the letter')

        response = self.client.get(self.group_url, {'l': first_letter.upper()})
        self.assertContains(response, self.contact_url)

        response = self.client.get(self.group_url, {'l': first_letter.lower()})
        self.assertContains(response, self.contact_url)

    def test_contact_creation(self):
        response = self.client.post(reverse('contacts:new_person'), {
                'name': 'New',
                'surname': 'Person',
                'msisdn': '27761234567',
                'groups': [TEST_GROUP_NAME],
                })
        contacts = self.contact_store.list_contacts()
        contact = max(contacts, key=lambda c: c.created_at)
        self.assertRedirects(response, reverse('contacts:person', kwargs={
            'person_key': contact.key,
        }))

    def test_contact_update(self):
        response = self.client.post(self.contact_url, {
            'name': 'changed name',
            'surname': 'changed surname',
            'msisdn': '112',
            'groups': [g.key for g in self.contact_store.list_groups()],
        })
        self.assertRedirects(response, self.contact_url)
        # reload to check
        contact = self.contact_store.get_contact_by_key(self.contact_key)
        self.assertEqual(contact.name, 'changed name')
        self.assertEqual(contact.surname, 'changed surname')
        self.assertEqual(contact.msisdn, '112')

    def test_contact_upload_into_new_group(self):
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'))
        response = self.client.post(reverse('contacts:people'), {
            'name': 'a new group',
            'file': csv_file,
        })
        group = self.contact_store.get_group(u"a new group")
        group_url = reverse('contacts:group', kwargs={'group_name': group.key})
        self.assertRedirects(response, group_url)
        self.assertEqual(len(group.backlinks.contacts()), 3)

    def test_contact_upload_into_existing_group(self):
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'))
        contact = self.contact_store.get_contact_by_key(self.contact_key)
        contact.groups.clear()
        contact.save()

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': TEST_GROUP_NAME,
            'file': csv_file,
        })
        self.assertRedirects(response, self.group_url)
        group = self.contact_store.get_group(TEST_GROUP_NAME)
        self.assertEqual(len(group.backlinks.contacts()), 3)

    def test_contact_upload_failure(self):
        response = self.client.post(reverse('contacts:people'), {
            'name': 'a new group',
            'file': None,
        })
        self.assertContains(response, 'Something went wrong with the upload')
        self.assertEqual(None, self.contact_store.get_group(u'a new group'))

    def test_contact_phone_number_normalization(self):
        settings.VUMI_COUNTRY_CODE = '27'
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-denormalized-contacts.csv'))
        response = self.client.post(reverse('contacts:people'), {
            'name': 'normalization group',
            'file': csv_file,
        })
        group = self.contact_store.get_group(u'normalization group')
        group_url = reverse('contacts:group', kwargs={'group_name': group.key})
        self.assertRedirects(response, group_url)
        self.assertTrue(all([c.msisdn.startswith('+27') for c
                             in group.backlinks.contacts()]))

    def test_contact_letter_filter(self):
        people_url = reverse('contacts:people')
        first_letter = TEST_CONTACT_SURNAME[0]

        # Assert that our name doesn't start with our "fail" case.
        self.assertNotEqual(first_letter.lower(), 'z')

        response = self.client.get(self.group_url, {'l': 'z'})
        self.assertContains(response, 'No contact surnames start with '
                                        'the letter')

        response = self.client.get(people_url, {'l': 'z'})
        self.assertContains(response, 'No contact surnames start with '
                                        'the letter')
        response = self.client.get(people_url, {'l': first_letter})
        self.assertContains(response, self.contact_url)

    def test_contact_querying(self):
        people_url = reverse('contacts:people')

        # test no-match
        response = self.client.get(people_url, {
            'q': 'this should not match',
        })
        self.assertContains(response, 'No contact match')

        # test match
        response = self.client.get(people_url, {
            'q': TEST_CONTACT_NAME,
        })
        self.assertContains(response, self.contact_url)
