# -*- coding: utf-8 -*-
from os import path
from StringIO import StringIO
from zipfile import ZipFile

from django.conf import settings
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.core import mail

from django.core.files.storage import default_storage
from go.contacts.parsers.base import FieldNormalizer
from go.base.tests.utils import VumiGoDjangoTestCase


TEST_GROUP_NAME = u"Test Group"
TEST_CONTACT_NAME = u"Name"
TEST_CONTACT_SURNAME = u"Surname"
TEST_CONTACT_MSISDN = u"+27761234567"


def newest(models):
    return max(models, key=lambda m: m.created_at)


def person_url(person_key):
    return reverse('contacts:person', kwargs={'person_key': person_key})


def group_url(group_key):
    return reverse('contacts:group', kwargs={'group_key': group_key})


def mkcontact(self, name=None, surname=None, msisdn=u'+1234567890', **kwargs):
    return self.contact_store.new_contact(
        name=unicode(name or TEST_CONTACT_NAME),
        surname=unicode(surname or TEST_CONTACT_SURNAME),
        msisdn=unicode(msisdn), **kwargs)


class ContactsTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(ContactsTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def test_redirect_index(self):
        response = self.client.get(reverse('contacts:index'))
        self.assertRedirects(response, reverse('contacts:groups'))

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
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        response = self.client.post(reverse('contacts:new_person'), {
            'name': 'New',
            'surname': 'Person',
            'msisdn': '27761234567',
            'groups': [group.key],
        })
        contact = self.get_latest_contact()
        self.assertRedirects(response, person_url(contact.key))

    def test_contact_deleting(self):
        contact = mkcontact(self)
        person_url = reverse('contacts:person', kwargs={
            'person_key': contact.key,
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
        contact = mkcontact(self)
        response = self.client.post(person_url(contact.key), {
            'name': 'changed name',
            'surname': 'changed surname',
            'msisdn': '112',
            'groups': [g.key for g in self.contact_store.list_groups()],
        })
        self.assertRedirects(response, person_url(contact.key))
        # reload to check
        contact = self.contact_store.get_contact_by_key(contact.key)
        self.assertEqual(contact.name, 'changed name')
        self.assertEqual(contact.surname, 'changed surname')
        self.assertEqual(contact.msisdn, '112')
        self.assertEqual(
            set(contact.groups.keys()),
            set([g.key for g in self.contact_store.list_groups()]))

    def specify_columns(self, group_key, columns=None):
        group_url = reverse('contacts:group', kwargs={
            'group_key': group_key,
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

        response = self.client.post(reverse('contacts:people'), {
            'file': csv_file,
            'name': 'a new group',
        })

        group = newest(self.contact_store.list_groups())
        self.assertEqual(group.name, u"a new group")
        self.assertRedirects(response, group_url(group.key))
        self.assertEqual(len(group.backlinks.contacts()), 0)

        self.specify_columns(group.key)
        self.assertEqual(len(group.backlinks.contacts()), 3)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_contact_upload_into_existing_group(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
                        'fixtures', 'sample-contacts.csv'), 'r')
        response = self.client.post(reverse('contacts:people'), {
            'file': csv_file,
            'contact_group': group.key
        })

        self.assertRedirects(response, group_url(group.key))
        group = self.contact_store.get_group(group.key)
        self.assertEqual(len(group.backlinks.contacts()), 0)
        self.specify_columns(group.key)
        self.assertEqual(len(group.backlinks.contacts()), 3)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_uploading_unicode_chars_in_csv(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
                                  'fixtures', 'sample-unicode-contacts.csv'))

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group.key,
            'file': csv_file,
        })
        self.assertRedirects(response, group_url(group.key))

        self.specify_columns(group.key)
        group = self.contact_store.get_group(group.key)
        self.assertEqual(len(group.backlinks.contacts()), 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_uploading_windows_linebreaks_in_csv(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
                                  'fixtures',
                                  'sample-windows-linebreaks-contacts.csv'))

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group.key,
            'file': csv_file,
        })
        self.assertRedirects(response, group_url(group.key))

        self.specify_columns(group.key, columns={
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
        group = self.contact_store.get_group(group.key)
        self.assertEqual(len(group.backlinks.contacts()), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_uploading_unicode_chars_in_csv_into_new_group(self):
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
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_contact_upload_from_group_page(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)

        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key
        })

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
        self.assertEqual(len(list(group.backlinks.contacts())), 0)

        # Now submit the column names and check that things have been written
        # to the db
        response = self.specify_columns(group.key)
        # Check the redirect
        self.assertRedirects(response, group_url)
        # 3 records should have been written to the db.
        self.assertEqual(len(list(group.backlinks.contacts())), 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_graceful_error_handling_on_upload_failure(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key
        })

        # Carefully crafted but bad CSV data
        wrong_file = StringIO(',,\na,b,c\n"')
        wrong_file.name = 'fubar.csv'

        response = self.client.post(group_url, {
            'file': wrong_file
        })

        response = self.client.get(group_url)
        self.assertContains(response, 'Something is wrong with the file')
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_contact_upload_failure(self):
        self.assertEqual(len(self.contact_store.list_groups()), 0)
        response = self.client.post(reverse('contacts:people'), {
            'name': 'a new group',
            'file': None,
        })
        self.assertContains(response, 'Something went wrong with the upload')
        self.assertEqual(len(self.contact_store.list_groups()), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

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
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

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

    def test_contact_querying(self):
        contact = mkcontact(self)
        people_url = reverse('contacts:people')

        # test no-match
        response = self.client.get(people_url, {
            'q': 'this should not match',
        })
        self.assertContains(response, 'No contacts match')

        # test match
        response = self.client.get(people_url, {
            'q': TEST_CONTACT_NAME,
        })
        self.assertContains(response, person_url(contact.key))

    def test_contact_key_value_query(self):
        contact = mkcontact(self)
        people_url = reverse('contacts:people')
        self.client.get(people_url, {
            'q': 'name:%s' % (contact.name,)
        })


class GroupsTestCase(VumiGoDjangoTestCase):
    # TODO: Cleaner test group and contact creation.

    use_riak = True

    def setUp(self):
        super(GroupsTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

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
        group = self.contact_store.new_group(u'old name')
        response = self.client.post(
            reverse('contacts:group', kwargs={'group_key': group.key}),
            {'name': 'new name', '_save_group': '1'})
        updated_group = self.contact_store.get_group(group.key)
        self.assertEqual('new name', updated_group.name)
        self.assertRedirects(response, group_url(group.key))

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
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        contact = mkcontact(self, groups=[group])
        # test no-match
        response = self.client.get(group_url(group.key), {
            'q': 'this should not match',
        })
        self.assertContains(response, 'No contacts match')

        # test match name
        response = self.client.get(group_url(group.key), {
            'q': TEST_CONTACT_NAME,
        })
        self.assertContains(response, person_url(contact.key))

    def test_group_contact_query_limits(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        default_limit = self.client.get(group_url(group.key), {
            'q': TEST_CONTACT_NAME,
        })
        custom_limit = self.client.get(group_url(group.key), {
            'q': TEST_CONTACT_NAME,
            'limit': 10,
        })
        no_limit = self.client.get(group_url(group.key), {
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

    def test_multiple_group_deletion(self):
        group_1 = self.contact_store.new_group(TEST_GROUP_NAME)
        group_2 = self.contact_store.new_group(TEST_GROUP_NAME)

        # Delete the groups
        groups_url = reverse('contacts:groups')
        response = self.client.post(groups_url, {
            'group': [group_1.key, group_2.key],
            '_delete': True,
        })
        self.assertEqual(self.contact_store.list_groups(), [])

    def test_group_deletion(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)

        # Create a contact in the group
        response = self.client.post(reverse('contacts:new_person'), {
            'name': 'New',
            'surname': 'Person',
            'msisdn': '27761234567',
            'groups': [group.key],
        })

        contact = self.get_latest_contact()
        self.assertRedirects(response, person_url(contact.key))

        # Delete the group
        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key,
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
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        # Create a contact in the group
        response = self.client.post(reverse('contacts:new_person'), {
            'name': 'New',
            'surname': 'Person',
            'msisdn': '27761234567',
            'groups': [group.key],
        })

        contact = self.get_latest_contact()
        self.assertRedirects(response, person_url(contact.key))

        # Clear the group
        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key,
        })
        response = self.client.post(group_url, {
            '_delete_group_contacts': True,
        })
        self.assertRedirects(response, group_url)

        self.assertEqual(
            self.contact_store.get_contacts_for_group(group), [])
        self.assertFalse(contact in self.contact_store.list_contacts())

    def test_group_contact_export(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        contact = mkcontact(self, groups=[group])
        # Clear the group
        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key,
        })

        # add some extra info to ensure it gets exported properly
        contact.extra['foo'] = u'bar'
        contact.extra['bar'] = u'baz'
        contact.save()

        response = self.client.post(group_url, {
            '_export_group_contacts': True,
        })

        self.assertRedirects(response, group_url)
        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(email.recipients(), [self.django_user.email])
        self.assertTrue(
            '%s contacts export' % (group.name,) in email.subject)
        self.assertTrue(
            '1 contact(s) from group "%s" attached' % (group.name,)
            in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        [header, contact, _] = csv_contents.split('\r\n')

        self.assertEqual(
            header,
            ','.join(['name', 'surname', 'email_address', 'msisdn', 'dob',
                      'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
                      'created_at', 'extras-bar', 'extras-foo']))

        self.assertTrue(contact.endswith('baz,bar'))
        self.assertTrue(contents)
        self.assertEqual(mime_type, 'application/zip')


class SmartGroupsTestCase(VumiGoDjangoTestCase):
    # TODO: Cleaner test group and contact creation.

    def setUp(self):
        super(SmartGroupsTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

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
        contact.add_to_group(group)
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
        contact = mkcontact(self)
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
        conversation = self.create_conversation()
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

        contact = mkcontact(self)
        group = newest(self.contact_store.list_groups())
        conversation = self.create_conversation()
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

        mkcontact(self, surname='bar'),
        mkcontact(self, name='foo'),
        match = mkcontact(self, name='foo', surname='bar')

        group = newest(self.contact_store.list_groups())
        conversation = self.create_conversation()
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

        contact1 = mkcontact(self, surname='bar')
        contact2 = mkcontact(self, name='foo')
        contact3 = mkcontact(self, name='foo', surname='bar')

        group = newest(self.contact_store.list_groups())
        conv = self.create_conversation()
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

    def test_smartgroup_contact_export(self):
        self.client.post(reverse('contacts:groups'), {
            'name': 'a smart group',
            'query': 'name:foo OR surname:bar',
            '_new_smart_group': '1',
        })

        mkcontact(self, surname='bar')
        mkcontact(self, name='foo')
        mkcontact(self, name='foo', surname='bar')

        group = newest(self.contact_store.list_groups())
        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key,
        })
        self.assertEqual(group.name, 'a smart group')
        response = self.client.post(group_url, {
            '_export_group_contacts': True,
        })

        contacts = self.contact_store.get_contacts_for_group(group)
        self.assertEqual(len(contacts), 3)

        self.assertRedirects(response, group_url)
        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        self.assertEqual(email.recipients(), [self.django_user.email])
        self.assertTrue(
            '%s contacts export' % (group.name,) in email.subject)
        self.assertTrue(
            '%s contact(s) from group "%s" attached' % (
                len(contacts), group.name) in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')
        self.assertTrue(csv_contents)
        self.assertEqual(mime_type, 'application/zip')


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
