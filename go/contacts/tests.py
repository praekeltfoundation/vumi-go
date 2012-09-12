# -*- coding: utf-8 -*-
from os import path
from StringIO import StringIO

from django.conf import settings
from django.test.client import Client
from django.core.urlresolvers import reverse

from go.base.models import User
from go.base.tests.utils import VumiGoDjangoTestCase
from go.vumitools.contact import ContactStore
from django.core import mail

TEST_GROUP_NAME = u"Test Group"
TEST_CONTACT_NAME = u"Name"
TEST_CONTACT_SURNAME = u"Surname"


def newest(models):
    return max(models, key=lambda m: m.created_at)


def person_url(person_key):
    return reverse('contacts:person', kwargs={'person_key': person_key})


def group_url(group_key):
    return reverse('contacts:group', kwargs={'group_key': group_key})


class ContactsTestCase(VumiGoDjangoTestCase):

    fixtures = ['test_user']

    def setUp(self):
        super(ContactsTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def setup_riak_fixtures(self):
        self.user = User.objects.get(username='username')
        self.contact_store = ContactStore.from_django_user(self.user)
        self.contact_store.contacts.enable_search()
        self.contact_store.groups.enable_search()

        # We need a group
        self.group = self.contact_store.new_group(TEST_GROUP_NAME)
        self.group_key = self.group.key

        # Also a contact
        self.contact = self.contact_store.new_contact(
            name=TEST_CONTACT_NAME, surname=TEST_CONTACT_SURNAME,
            msisdn=u"+27761234567")
        self.contact.add_to_group(self.group)
        self.contact.save()
        self.contact_key = self.contact.key

    def test_redirect_index(self):
        response = self.client.get(reverse('contacts:index'))
        self.assertRedirects(response, reverse('contacts:groups'))

    def test_groups_creation(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': 'a new group',
        })
        group = newest(self.contact_store.list_groups())
        self.assertNotEqual(group, None)
        self.assertEqual(u'a new group', group.name)
        self.assertRedirects(response, group_url(group.key))

    def test_groups_creation_with_funny_chars(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': "a new group! with cüte chars's",
        })
        group = newest(self.contact_store.list_groups())
        self.assertNotEqual(group, None)
        self.assertEqual(u"a new group! with cüte chars's", group.name)
        self.assertRedirects(response, group_url(group.key))

    def test_group_contact_querying(self):
        # test no-match
        response = self.client.get(group_url(self.group_key), {
            'q': 'this should not match',
        })
        self.assertContains(response, 'No contact match')

        # test match name
        response = self.client.get(group_url(self.group_key), {
            'q': TEST_CONTACT_NAME,
        })
        self.assertContains(response, person_url(self.contact_key))

        # test match surname
        response = self.client.get(group_url(self.group_key), {
            'q': TEST_CONTACT_SURNAME,
        })
        self.assertContains(response, person_url(self.contact_key))

    def test_group_contact_filter_by_letter(self):
        first_letter = TEST_CONTACT_SURNAME[0]

        # Assert that our name doesn't start with our "fail" case.
        self.assertNotEqual(first_letter.lower(), 'z')

        response = self.client.get(group_url(self.group_key), {'l': 'z'})
        self.assertContains(response, 'No contact surnames start with '
                                        'the letter')

        response = self.client.get(group_url(self.group_key),
                                   {'l': first_letter.upper()})
        self.assertContains(response, person_url(self.contact_key))

        response = self.client.get(group_url(self.group_key),
                                   {'l': first_letter.lower()})
        self.assertContains(response, person_url(self.contact_key))

    def test_contact_creation(self):
        response = self.client.post(reverse('contacts:new_person'), {
                'name': 'New',
                'surname': 'Person',
                'msisdn': '27761234567',
                'groups': [self.group_key],
                })
        contacts = self.contact_store.list_contacts()
        contact = max(contacts, key=lambda c: c.created_at)
        self.assertRedirects(response, person_url(contact.key))

    def test_contact_deleting(self):
        person_url = reverse('contacts:person', kwargs={
            'person_key': self.contact.key,
            })
        response = self.client.post(person_url, {
            '_delete_contact': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith(
            reverse('contacts:index')))

        # After deleting the person should return a 404 page
        response = self.client.get(person_url)
        self.assertEqual(response.status_code, 404)

    def test_contact_update(self):
        response = self.client.post(person_url(self.contact_key), {
            'name': 'changed name',
            'surname': 'changed surname',
            'msisdn': '112',
            'groups': [g.key for g in self.contact_store.list_groups()],
        })
        self.assertRedirects(response, person_url(self.contact_key))
        # reload to check
        contact = self.contact_store.get_contact_by_key(self.contact_key)
        self.assertEqual(contact.name, 'changed name')
        self.assertEqual(contact.surname, 'changed surname')
        self.assertEqual(contact.msisdn, '112')
        self.assertEqual(set([g.key for g in contact.groups.get_all()]),
                    set([g.key for g in self.contact_store.list_groups()]))

    def test_group_deletion(self):
        # Create a contact in the group
        response = self.client.post(reverse('contacts:new_person'), {
            'name': 'New',
            'surname': 'Person',
            'msisdn': '27761234567',
            'groups': [self.group_key],
            })

        contacts = self.contact_store.list_contacts()
        contact = max(contacts, key=lambda c: c.created_at)
        self.assertRedirects(response, person_url(contact.key))

        # Delete the group
        group_url = reverse('contacts:group', kwargs={
            'group_key': self.group.key,
        })
        response = self.client.post(group_url, {
                '_delete_group': True,
            })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith(
            reverse('contacts:index')))

        reloaded_contacts = self.contact_store.list_contacts()
        reloaded_contact = max(reloaded_contacts, key=lambda c: c.created_at)
        self.assertEqual(reloaded_contact.key, contact.key)
        self.assertEqual(reloaded_contact.groups.get_all(), [])

    def clear_groups(self, contact_key=None):
        contact = self.contact_store.get_contact_by_key(
            contact_key or self.contact_key)
        contact.groups.clear()
        contact.save()

    def specify_columns(self, group_key=None, columns=None):
        group_url = reverse('contacts:group', kwargs={
            'group_key': group_key or self.group_key
        })
        defaults = {
            'column-0': 'name',
            'column-1': 'surname',
            'column-2': 'msisdn',
            '_complete_csv_upload': '1',
        }
        if columns:
            defaults.update(columns)
        return self.client.post(group_url, defaults)

    def test_contact_upload_into_new_group(self):
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'))

        self.clear_groups()
        response = self.client.post(reverse('contacts:people'), {
            'file': csv_file,
            'name': 'a new group',
        })

        group = newest(self.contact_store.list_groups())
        self.assertEqual(group.name, u"a new group")
        self.assertRedirects(response, group_url(group.key))
        self.assertEqual(len(group.backlinks.contacts()), 0)

        self.specify_columns(group_key=group.key)
        self.assertEqual(len(group.backlinks.contacts()), 3)

    def test_contact_upload_into_existing_group(self):
        self.clear_groups()
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'), 'r')
        response = self.client.post(reverse('contacts:people'),
            {
                'file': csv_file,
                'contact_group': self.group_key
            }
        )

        self.assertRedirects(response, group_url(self.group_key))
        group = self.contact_store.get_group(self.group_key)
        self.assertEqual(len(group.backlinks.contacts()), 0)

        self.specify_columns()
        self.assertEqual(len(group.backlinks.contacts()), 3)

    def test_uploading_unicode_chars_in_csv(self):
        self.clear_groups()
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-unicode-contacts.csv'))

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': self.group_key,
            'file': csv_file,
        })
        self.assertRedirects(response, group_url(self.group_key))

        self.specify_columns()
        group = self.contact_store.get_group(self.group_key)
        self.assertEqual(len(group.backlinks.contacts()), 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)

    def test_uploading_windows_linebreaks_in_csv(self):
        self.clear_groups()
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-windows-linebreaks-contacts.csv'))

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': self.group_key,
            'file': csv_file,
        })
        self.assertRedirects(response, group_url(self.group_key))

        self.specify_columns(columns={
            'column-0': 'msisdn',
            'column-1': 'area',
            'column-2': 'nairobi_1',
            'column-3': 'baba dogo',
            'column-4': 'age',
            'column-5': 'gender',
            'column-6': 'language',
            'column-7': 'occupation',
            })
        group = self.contact_store.get_group(self.group_key)
        self.assertEqual(len(group.backlinks.contacts()), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)

    def test_uploading_unicode_chars_in_csv_into_new_group(self):
        self.clear_groups()
        new_group_name = u'Testing a ünicode grøüp'
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-unicode-contacts.csv'))

        response = self.client.post(reverse('contacts:people'), {
            'name': new_group_name,
            'file': csv_file,
        })

        group = newest(self.contact_store.list_groups())
        self.assertEqual(group.name, new_group_name)
        self.assertRedirects(response, group_url(group.key))
        self.specify_columns(group_key=group.key)
        self.assertEqual(len(group.backlinks.contacts()), 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)

    def test_contact_upload_from_group_page(self):

        group_url = reverse('contacts:group', kwargs={
            'group_key': self.group_key
        })

        self.clear_groups()
        csv_file = open(
            path.join(settings.PROJECT_ROOT, 'base',
                'fixtures', 'sample-contacts.csv'), 'r')
        response = self.client.post(group_url, {
            'file': csv_file,
        })

        # It should redirect to the group page
        self.assertRedirects(response, group_url)

        # Wich should show the column-matching dialogue
        response = self.client.get(group_url)
        self.assertContains(response,
            'Please match the sample to the fields provided')

        # The path of the uploaded file should have been set
        self.assertTrue('uploaded_csv_path' in self.client.session)

        # And it should store the first two lines as sample data
        # in the session in order to do the CSV column matching.
        csv_file.seek(0)
        expected_two_lines = '\n'.join([csv_file.readline().strip()
                                            for i in range(2)])
        first_two_lines = self.client.session['uploaded_csv_data']
        self.assertEqual(first_two_lines, expected_two_lines)

        # Nothing should have been written to the db by now.
        self.assertEqual(len(list(self.group.backlinks.contacts())), 0)

        # Now submit the column names and check that things have been written
        # to the db
        response = self.specify_columns()
        # Check the redirect
        self.assertRedirects(response, group_url)
        # 3 records should have been written to the db.
        self.assertEqual(len(list(self.group.backlinks.contacts())), 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)

    def test_graceful_error_handling_on_upload_failure(self):
        group_url = reverse('contacts:group', kwargs={
            'group_key': self.group_key
        })

        wrong_file = StringIO('fubar')
        wrong_file.name = 'fubar.csv'

        self.clear_groups()

        response = self.client.post(group_url, {
            'file': wrong_file
            })

        response = self.specify_columns()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Something is wrong with the file')

    def test_contact_upload_failure(self):
        self.assertEqual(len(self.contact_store.list_groups()), 1)
        response = self.client.post(reverse('contacts:people'), {
            'name': 'a new group',
            'file': None,
        })
        self.assertContains(response, 'Something went wrong with the upload')
        self.assertEqual(len(self.contact_store.list_groups()), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_parsing_failure(self):
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-broken-contacts.csv'))
        response = self.client.post(reverse('contacts:people'), {
            'name': 'broken contacts group',
            'file': csv_file,
        })
        group = newest(self.contact_store.list_groups())
        self.assertRedirects(response, group_url(group.key))
        response = self.specify_columns(group_key=group.key)
        group = newest(self.contact_store.list_groups())
        contacts = group.backlinks.contacts()
        self.assertEqual(len(contacts), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('went wrong' in mail.outbox[0].subject)

    def test_contact_letter_filter(self):
        people_url = reverse('contacts:people')
        first_letter = TEST_CONTACT_SURNAME[0]

        # Assert that our name doesn't start with our "fail" case.
        self.assertNotEqual(first_letter.lower(), 'z')

        response = self.client.get(group_url(self.group_key), {'l': 'z'})
        self.assertContains(response, 'No contact surnames start with '
                                        'the letter')

        response = self.client.get(people_url, {'l': 'z'})
        self.assertContains(response, 'No contact surnames start with '
                                        'the letter')
        response = self.client.get(people_url, {'l': first_letter})
        self.assertContains(response, person_url(self.contact_key))

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
        self.assertContains(response, person_url(self.contact_key))

    def test_contact_key_value_query(self):
        people_url = reverse('contacts:people')
        self.client.get(people_url, {
            'q': 'name:%s' % (self.contact.name,)
        })
