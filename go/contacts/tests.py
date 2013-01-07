# -*- coding: utf-8 -*-
from os import path
from StringIO import StringIO

from django.conf import settings
from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase
from django.core import mail

from go.contacts.parsers.base import FieldNormalizer

TEST_GROUP_NAME = u"Test Group"
TEST_CONTACT_NAME = u"Name"
TEST_CONTACT_SURNAME = u"Surname"


def newest(models):
    return max(models, key=lambda m: m.created_at)


def person_url(person_key):
    return reverse('contacts:person', kwargs={'person_key': person_key})


def group_url(group_key):
    return reverse('contacts:group', kwargs={'group_key': group_key})


class ContactsTestCase(DjangoGoApplicationTestCase):

    fixtures = ['test_user']

    def setUp(self):
        super(ContactsTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def test_redirect_index(self):
        response = self.client.get(reverse('contacts:index'))
        self.assertRedirects(response, reverse('contacts:groups'))

    def clear_groups(self, contact_key=None):
        contact = self.contact_store.get_contact_by_key(
            contact_key or self.contact_key)
        contact.groups.clear()
        contact.save()

    def get_all_contacts(self, keys=None):
        if keys is None:
            keys = self.contact_store.list_contacts()
        contacts = []
        for batch in self.contact_store.contacts.load_all_bunches(keys):
            contacts.extend(batch)
        return contacts

    def get_latest_contact(self):
        return max(self.get_all_contacts(), key=lambda c: c.created_at)

    def test_contact_creation(self):
        response = self.client.post(reverse('contacts:new_person'), {
                'name': 'New',
                'surname': 'Person',
                'msisdn': '27761234567',
                'groups': [self.group_key],
                })
        contact = self.get_latest_contact()
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
        self.assertEqual(set(contact.groups.keys()),
                    set([g.key for g in self.contact_store.list_groups()]))

    def specify_columns(self, group_key=None, columns=None):
        group_url = reverse('contacts:group', kwargs={
            'group_key': group_key or self.group_key
        })
        defaults = {
            'column-0': 'name',
            'column-1': 'surname',
            'column-2': 'msisdn',
            'normalize-0': '',
            'normalize-1': '',
            'normalize-2': '',
            '_complete_contact_upload': '1',
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
            'normalize-0': '',
            'normalize-1': '',
            'normalize-2': '',
            'normalize-3': '',
            'normalize-4': '',
            'normalize-5': '',
            'normalize-6': '',
            'normalize-7': '',
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
        self.assertTrue('uploaded_contacts_file_name' in self.client.session)
        self.assertTrue('uploaded_contacts_file_path' in self.client.session)

        file_name = self.client.session['uploaded_contacts_file_name']
        self.assertEqual(file_name, 'sample-contacts.csv')

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

        # Carefully crafted but bad CSV data
        wrong_file = StringIO(',,\na,b,c\n"')
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
        response = self.specify_columns(group_key=group.key, columns={
            'column-0': 'name',
            'column-1': 'surname',
            'column-2': 'msisdn',
            'normalize-0': '',
            'normalize-1': '',
            'normalize-2': '',
            })
        group = newest(self.contact_store.list_groups())
        contacts = group.backlinks.contacts()
        self.assertEqual(len(contacts), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('went wrong' in mail.outbox[0].subject)

    def test_normalization(self):
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-non-normalized-contacts.csv'))
        response = self.client.post(reverse('contacts:people'), {
            'name': 'non-normalized-contacts',
            'file': csv_file,
            })
        group = newest(self.contact_store.list_groups())
        self.assertRedirects(response, group_url(group.key))
        response = self.specify_columns(group_key=group.key, columns={
            'column-0': 'name',
            'column-1': 'surname',
            'column-2': 'integer',
            'column-3': 'float',
            'column-4': 'msisdn',
            'normalize-0': 'string',
            'normalize-1': 'string',
            'normalize-2': 'integer',
            'normalize-3': 'float',
            'normalize-4': 'msisdn_za',
            })
        contacts = self.get_all_contacts(group.backlinks.contacts())

        self.assertTrue(all([contact.msisdn == '+27761234561' for contact in
            contacts]))
        self.assertTrue(all([contact.extra['integer'] == '2' for contact in
            contacts]))
        self.assertTrue(all([contact.extra['float'] == '2.0' for contact in
            contacts]))

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

    def test_contact_for_addr(self):
        sms_contact = self.mkcontact(msisdn=u'+270000000')
        twitter_contact = self.mkcontact(twitter_handle=u'@someone')
        gtalk_contact = self.mkcontact(gtalk_id=u'gtalk@host.com')

        self.assertEqual(
            self.contact_store.contact_for_addr('sms', '+270000000').key,
            sms_contact.key)
        self.assertEqual(
            self.contact_store.contact_for_addr('ussd', '+270000000').key,
            sms_contact.key)
        self.assertEqual(
            self.contact_store.contact_for_addr('twitter', '@someone').key,
            twitter_contact.key)
        self.assertEqual(
            self.contact_store.contact_for_addr('gtalk', 'gtalk@host.com').key,
            gtalk_contact.key)
        self.assertRaisesRegexp(RuntimeError, 'Unsupported transport_type',
            self.contact_store.contact_for_addr, 'unknown', 'unknown')


class GroupsTestCase(DjangoGoApplicationTestCase):

    fixtures = ['test_user']

    def setUp(self):
        super(GroupsTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_all_contacts(self, keys=None):
        if keys is None:
            keys = self.contact_store.list_contacts()
        contacts = []
        for batch in self.contact_store.contacts.load_all_bunches(keys):
            contacts.extend(batch)
        return contacts

    def get_latest_contact(self):
        return max(self.get_all_contacts(), key=lambda c: c.created_at)

    def test_groups_creation(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': 'a new group',
            '_new_group': '1',
        })
        group = newest(self.contact_store.list_groups())
        self.assertNotEqual(group, None)
        self.assertEqual(u'a new group', group.name)
        self.assertRedirects(response, group_url(group.key))

    def test_group_updating(self):
        new_group_name = 'a new group name'
        self.assertNotEqual(self.group.name, new_group_name)
        response = self.client.post(
            reverse('contacts:group', kwargs={'group_key': self.group.key}),
            {'name': new_group_name, '_save_group': '1'})
        updated_group = self.contact_store.get_group(self.group.key)
        self.assertEqual(new_group_name, updated_group.name)
        self.assertRedirects(response, group_url(self.group.key))

    def test_groups_creation_with_funny_chars(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': "a new group! with cüte chars's",
            '_new_group': '1',
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

    def test_group_contact_query_limits(self):
        default_limit = self.client.get(group_url(self.group_key), {
            'q': TEST_CONTACT_NAME,
        })
        custom_limit = self.client.get(group_url(self.group_key), {
            'q': TEST_CONTACT_NAME,
            'limit': 10,
        })
        no_limit = self.client.get(group_url(self.group_key), {
            'q': TEST_CONTACT_NAME,
            'limit': 0,
        })
        self.assertContains(default_limit, 'alert-success')
        self.assertContains(default_limit, 'Showing up to 100 random contacts')
        self.assertContains(custom_limit, 'alert-success')
        self.assertContains(custom_limit, 'Showing up to 10 random contacts')
        # Testing for CSS class not existing (since that's used to display
        # notification messages). We cannot check the context for messages
        # since that uses Django's internal messages framework which cleared
        # during rendering.
        self.assertNotContains(no_limit, 'alert-success')

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

    def test_group_deletion(self):
        # Create a contact in the group
        response = self.client.post(reverse('contacts:new_person'), {
            'name': 'New',
            'surname': 'Person',
            'msisdn': '27761234567',
            'groups': [self.group_key],
            })

        contact = self.get_latest_contact()
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

        reloaded_contact = self.get_latest_contact()
        self.assertEqual(reloaded_contact.key, contact.key)
        self.assertEqual(reloaded_contact.groups.keys(), [])

    def test_group_clearing(self):
        # Create a contact in the group
        response = self.client.post(reverse('contacts:new_person'), {
            'name': 'New',
            'surname': 'Person',
            'msisdn': '27761234567',
            'groups': [self.group_key],
            })

        contact = self.get_latest_contact()
        self.assertRedirects(response, person_url(contact.key))

        # Clear the group
        group_url = reverse('contacts:group', kwargs={
            'group_key': self.group.key,
        })
        response = self.client.post(group_url, {
                '_delete_group_contacts': True,
            })
        self.assertRedirects(response, group_url)

        self.assertEqual(
            self.contact_store.get_contacts_for_group(self.group), [])
        self.assertFalse(contact in self.contact_store.list_contacts())


class SmartGroupsTestCase(DjangoGoApplicationTestCase):

    fixtures = ['test_user']

    def setUp(self):
        super(SmartGroupsTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def mksmart_group(self, query, name='a smart group'):
        response = self.client.post(reverse('contacts:groups'), {
            'name': name,
            'query': query,
            '_new_smart_group': '1',
            })
        group = newest(self.contact_store.list_groups())
        self.assertRedirects(response, group_url(group.key))
        return group

    def add_to_group(self, contact, group):
        contact.add_to_group(self.group)
        contact.save()
        return contact

    def test_smart_groups_creation(self):
        group = self.mksmart_group('msisdn:\+12*')
        self.assertEqual(u'a smart group', group.name)
        self.assertEqual(u'msisdn:\+12*', group.query)

    def test_smart_group_deletion(self):
        group = self.mksmart_group('msisdn:\+12*')
        response = self.client.post(
            reverse('contacts:group', kwargs={'group_key': group.key}),
            {'_delete_group': 1})
        self.assertRedirects(response, reverse('contacts:index'),
            target_status_code=302)
        self.assertTrue(group not in self.contact_store.list_groups())

    def test_smart_group_clearing(self):
        contact = self.mkcontact()
        group = self.mksmart_group('msisdn:\+12*')
        self.assertEqual([contact.key],
            self.contact_store.get_contacts_for_group(group))
        response = self.client.post(
            reverse('contacts:group', kwargs={'group_key': group.key}),
            {'_delete_group_contacts': 1})
        self.assertRedirects(response, reverse('contacts:group', kwargs={
            'group_key': group.key}))
        self.assertEqual(
            [], self.contact_store.get_contacts_for_group(group))

    def test_smart_group_updating(self):
        group = self.mksmart_group('msisdn:\+12*')
        response = self.client.post(
            reverse('contacts:group', kwargs={'group_key': group.key}),
            {'name': 'foo', 'query': 'name:bar', '_save_group': 1})
        self.assertRedirects(response, reverse('contacts:group', kwargs={
            'group_key': group.key}))
        saved_group = self.contact_store.get_group(group.key)
        self.assertEqual(saved_group.name, 'foo')
        self.assertEqual(saved_group.query, 'name:bar')

    def test_smart_groups_no_matches_results(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': 'a smart group',
            'query': 'msisdn:\+12*',
            '_new_smart_group': '1',
            })
        group = newest(self.contact_store.list_groups())
        conversation = self.mkconversation()
        conversation.groups.add(group)
        conversation.save()

        self.assertRedirects(response, group_url(group.key))
        self.assertEqual(u'a smart group', group.name)
        self.assertEqual(u'msisdn:\+12*', group.query)
        self.assertEqual(
            self.contact_store.get_contacts_for_conversation(conversation),
            [])

    def test_smart_groups_with_matches_results(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': 'a smart group',
            'query': 'msisdn:\+12*',
            '_new_smart_group': '1',
            })

        contact = self.mkcontact()
        group = newest(self.contact_store.list_groups())
        conversation = self.mkconversation()
        conversation.groups.add(group)
        conversation.save()

        self.assertRedirects(response, group_url(group.key))
        self.assertEqual(u'a smart group', group.name)
        self.assertEqual(u'msisdn:\+12*', group.query)
        self.assertEqual(
            self.contact_store.get_static_contacts_for_group(group), [])
        self.assertEqual(
            self.contact_store.get_dynamic_contacts_for_group(group),
            [contact.key])
        self.assertEqual(
            self.contact_store.get_contacts_for_conversation(conversation),
            [contact.key])

    def test_smart_groups_with_matches_AND_query_results(self):
        self.client.post(reverse('contacts:groups'), {
            'name': 'a smart group',
            'query': 'name:foo AND surname:bar',
            '_new_smart_group': '1',
            })

        self.mkcontact(surname='bar'),
        self.mkcontact(name='foo'),
        match = self.mkcontact(name='foo', surname='bar')

        group = newest(self.contact_store.list_groups())
        conversation = self.mkconversation()
        conversation.groups.add(group)
        conversation.save()

        contacts = self.contact_store.get_contacts_for_conversation(
            conversation)
        self.assertEqual(contacts, [match.key])

    def test_smart_groups_with_matches_OR_query_results(self):
        self.client.post(reverse('contacts:groups'), {
            'name': 'a smart group',
            'query': 'name:foo OR surname:bar',
            '_new_smart_group': '1',
            })

        contact1 = self.mkcontact(surname='bar')
        contact2 = self.mkcontact(name='foo')
        contact3 = self.mkcontact(name='foo', surname='bar')

        group = newest(self.contact_store.list_groups())
        conv = self.mkconversation()
        conv.groups.add(group)
        conv.save()

        self.assertEqual(
            set(self.contact_store.get_contacts_for_conversation(conv)),
            set([contact1.key, contact2.key, contact3.key]))

    def test_smart_group_limit(self):
        self.client.post(reverse('contacts:groups'), {
            'name': 'a smart group',
            'query': 'name:foo OR surname:bar',
            '_new_smart_group': '1',
            })
        group = newest(self.contact_store.list_groups())
        default_limit = self.client.get('%s?query=foo:bar' % (
            reverse('contacts:group', kwargs={
            'group_key': group.key,
            }),))
        custom_limit = self.client.get('%s?query=foo:bar&limit=10' % (
            reverse('contacts:group', kwargs={
            'group_key': group.key,
            }),))
        no_limit = self.client.get('%s?query=foo:bar&limit=0' % (
            reverse('contacts:group', kwargs={
            'group_key': group.key,
            }),))

        self.assertContains(default_limit, 'alert-success')
        self.assertContains(default_limit, 'Showing up to 100 random contacts')
        self.assertContains(custom_limit, 'alert-success')
        self.assertContains(custom_limit, 'Showing up to 10 random contacts')
        # Testing for CSS class not existing (since that's used to display
        # notification messages). We cannot check the context for messages
        # since that uses Django's internal messages framework which cleared
        # during rendering.
        self.assertNotContains(no_limit, 'alert-success')


class TestFieldNormalizer(TestCase):

    def setUp(self):
        self.fn = FieldNormalizer()

    def assertNormalizedMsisdn(self, country_code, value, expected,
                               instance_type=unicode):
        normalized = self.fn.do_msisdn(value, country_code)
        self.assertEqual(normalized, expected)
        self.assertTrue(isinstance(normalized, instance_type))

    def assertNormalized(self, name, value, expected, instance_type=None):
        normalized = self.fn.normalize(name, value)
        self.assertEqual(normalized, expected)
        if instance_type:
            self.assertTrue(isinstance(normalized, instance_type))

    def test_msisdns(self):
        self.assertNormalizedMsisdn('27', '761234567', '+27761234567')
        self.assertNormalizedMsisdn('27', '761234567.0', '+27761234567')
        self.assertNormalizedMsisdn('27', '0761234567', '+27761234567')
        self.assertNormalizedMsisdn('27', '27761234567', '+27761234567')
        self.assertNormalizedMsisdn('27', '0027761234567', '+27761234567')
        self.assertNormalizedMsisdn('27', '+27761234567', '+27761234567')
        self.assertNormalizedMsisdn('27', 761234567, '+27761234567')
        self.assertNormalizedMsisdn('27', 761234567.0, '+27761234567')
        self.assertNormalizedMsisdn('27', 27761234567, '+27761234567')
        self.assertNormalizedMsisdn('27', 2.74727E+10, '+27472700000')
        self.assertNormalizedMsisdn('27', '2.74727E+10', '+27472700000')

    def test_internationalized_msisdn(self):
        self.assertNormalized('msisdn_int', '0027761234567', '+27761234567',
            unicode)
        self.assertNormalized('msisdn_int', '27761234567', '+27761234567',
            unicode)
        self.assertNormalized('msisdn_int', 27761234567, '+27761234567',
            unicode)
        self.assertNormalized('msisdn_int', '+27761234567', '+27761234567',
            unicode)
        self.assertNormalized('msisdn_int', '2.74727E+10', '+27472700000')
        self.assertNormalized('msisdn_int', 2.74727E+10, '+27472700000')

    def test_integer(self):
        self.assertNormalized('integer', '0.1', 0, int)
        self.assertNormalized('integer', '1.1', 1, int)
        self.assertNormalized('integer', 2.1, 2, int)
        self.assertNormalized('integer', '', '', str)
        self.assertNormalized('integer', 'None', 'None', str)
        self.assertNormalized('integer', None, None)

    def test_float(self):
        self.assertNormalized('float', '0.1', 0.1, float)
        self.assertNormalized('float', '1.1', 1.1, float)
        self.assertNormalized('float', 2.1, 2.1, float)
        self.assertNormalized('float', '', '', str)
        self.assertNormalized('float', 'None', 'None', str)
        self.assertNormalized('float', None, None)

    def test_string(self):
        self.assertNormalized('string', 761234567.0, '761234567.0', unicode)
        self.assertNormalized('string', '1.1', '1.1', unicode)
        self.assertNormalized('string', '', '', unicode)
        self.assertNormalized('string', 'None', 'None', unicode)
        self.assertNormalized('string', None, None)

    def test_unknown(self):
        self.assertNormalized('foo', 761234567.0, 761234567.0, float)
        self.assertNormalized('bar', '1.1', '1.1', str)
        self.assertNormalized('bas', u'1.1', u'1.1', unicode)
        self.assertNormalized('baz', '', '', str)
        self.assertNormalized('fubar', 'None', 'None', str)
        self.assertNormalized('zab', None, None)
