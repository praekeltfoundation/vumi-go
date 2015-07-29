# -*- coding: utf-8 -*-
import csv
import os
import tempfile
from datetime import datetime
from os import path
from StringIO import StringIO
from zipfile import ZipFile

from django.conf import settings
from django.core import mail
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse
from django.utils.html import escape
from django.templatetags.l10n import localize

from go.contacts.parsers.base import FieldNormalizer
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


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


def get_all_contact_keys_for_group(contact_store, group):
    """
    Walk the index pages returned from get_contact_keys_for_group() and collect
    all the keys.
    """
    keys = []
    index_page = contact_store.get_contact_keys_for_group(group)
    while index_page is not None:
        keys.extend(index_page)
        index_page = index_page.next_page()
    return keys


class BaseContactsTestCase(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user_email = self.user_helper.get_django_user().email
        self.contact_store = self.user_helper.user_api.contact_store
        self.client = self.vumi_helper.get_client()
        self.clear_tmp_storage()

    def clear_tmp_storage(self):
        try:
            _folders, files = default_storage.listdir("tmp")
        except (NotImplementedError, OSError):
            # exceptions indicated that listdir is not supported by
            # default storage or tmp does not yet exist.
            files = []
        for filename in files:
            default_storage.delete(path.join("tmp", filename))

    def mkcontact(self, name=None, surname=None, msisdn=u'+1234567890',
                  **kwargs):
        return self.contact_store.new_contact(
            name=unicode(name or TEST_CONTACT_NAME),
            surname=unicode(surname or TEST_CONTACT_SURNAME),
            msisdn=unicode(msisdn), **kwargs)

    def get_group_contact_keys(self, group):
        contact_keys = []
        contact_keys_page = group.backlinks.contact_keys()
        while contact_keys_page is not None:
            contact_keys.extend(contact_keys_page)
            contact_keys_page = contact_keys_page.next_page()
        return contact_keys

    def assert_group_contacts_count(self, group, count):
        contact_keys = self.get_group_contact_keys(group)
        self.assertEqual(len(contact_keys), count)


class TestContacts(BaseContactsTestCase):
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

    def test_contact_details(self):
        group_1 = self.contact_store.new_group(u'lerp')
        group_2 = self.contact_store.new_group(u'larp')

        contact = self.mkcontact(
            name='Foo',
            surname='Bar',
            groups=[group_1, group_2],
            extra={'black': 'moth', 'super': 'rainbow'})

        response = self.client.get(person_url(contact.key))

        self.assertContains(
            response,
            "Contact record created at %s." % localize(contact.created_at))

        self.assertContains(response, 'Foo')
        self.assertContains(response, 'Bar')

        self.assertContains(response, 'lerp')
        self.assertContains(response, 'larp')

        self.assertContains(response, 'Extra details')
        self.assertContains(response, 'black')
        self.assertContains(response, 'moth')
        self.assertContains(response, 'super')
        self.assertContains(response, 'rainbow')

        self.assertNotContains(response, 'Subscriptions')

    def test_subscriptions(self):
        contact = self.mkcontact(
            name='Foo',
            surname='Bar',
            subscription={'app_sub_1': 1, 'app_sub_2': 2})

        response = self.client.get(person_url(contact.key))

        self.assertContains(response, 'Subscriptions')
        self.assertContains(response, 'app_sub_1')
        self.assertContains(response, '1')
        self.assertContains(response, 'app_sub_2')
        self.assertContains(response, '2')

        self.assertNotContains(response, 'Extra details')

    def test_contact_creation_form(self):
        response = self.client.get(reverse('contacts:new_person'))
        for label in ["Name", "Surname", "Email address", "Groups"]:
            self.assertContains(response, label)
        self.assertNotContains(response, "Contact record created at")

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
        contact = self.mkcontact()
        person_url = reverse('contacts:person', kwargs={
            'person_key': contact.key,
        })
        response = self.client.post(person_url, {
            '_delete': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith(
            reverse('contacts:people')))

        # After deleting the person should return a 404 page
        response = self.client.get(person_url)
        self.assertEqual(response.status_code, 404)

    def test_contact_update(self):
        contact = self.mkcontact()
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

    def test_list_contacts(self):
        """
        When we have fewer contacts than the default limit, the response
        contains all of them.
        """
        contacts = [self.mkcontact(), self.mkcontact()]
        ckeys = sorted(c.key for c in contacts)

        response = self.client.get(reverse('contacts:people'), {})
        response_contacts = response.context['selected_contacts']
        self.assertEqual(ckeys, sorted(c.key for c in response_contacts))
        self.assertContains(response, "Showing 2 of 2 contact(s)")
        self.assertContains(response, ckeys[0])
        self.assertContains(response, ckeys[1])

    def test_list_contacts_within_limit(self):
        """
        When we have fewer contacts than the specified limit, the response
        contains all of them.
        """
        contacts = [self.mkcontact(), self.mkcontact(), self.mkcontact()]
        ckeys = sorted(c.key for c in contacts)

        response = self.client.get(reverse('contacts:people'), {'limit': 5})
        response_contacts = response.context['selected_contacts']
        self.assertEqual(ckeys, sorted(c.key for c in response_contacts))
        self.assertContains(response, "Showing 3 of 3 contact(s)")
        self.assertContains(response, ckeys[0])
        self.assertContains(response, ckeys[1])
        self.assertContains(response, ckeys[2])

    def test_list_contacts_limit(self):
        """
        When we have more contacts than the limit, the response only contains
        a subset of the contacts.
        """
        contacts = [self.mkcontact(), self.mkcontact(), self.mkcontact()]
        ckeys = sorted(c.key for c in contacts)

        response = self.client.get(reverse('contacts:people'), {'limit': 2})
        response_contacts = response.context['selected_contacts']
        # This assumes we're using raw index pagination (which sorts by key)
        # under the hood.
        self.assertEqual(ckeys[:2], sorted(c.key for c in response_contacts))
        self.assertContains(response, "Showing 2 of 3 contact(s)")
        self.assertContains(response, ckeys[0])
        self.assertContains(response, ckeys[1])
        self.assertNotContains(response, ckeys[2])

    def test_list_contacts_fetch_limit(self):
        """
        When we have more contacts than the fetch limit, the response only
        contains a subset of the contacts and doesn't display the total number
        of contacts.
        """
        contacts = [self.mkcontact(), self.mkcontact(), self.mkcontact()]
        ckeys = sorted(c.key for c in contacts)

        response = self.client.get(
            reverse('contacts:people'), {'limit': 1, '_fetch_limit': 2})
        response_contacts = response.context['selected_contacts']
        # This assumes we're using raw index pagination (which sorts by key)
        # under the hood.
        self.assertEqual(ckeys[:1], sorted(c.key for c in response_contacts))
        self.assertContains(response, "Showing 1 of 2+ contact(s)")
        self.assertContains(response, ckeys[0])
        self.assertNotContains(response, ckeys[1])
        self.assertNotContains(response, ckeys[2])

    def test_contact_exporting(self):
        c1 = self.mkcontact()
        c1.extra['foo'] = u'bar'
        c1.extra['bar'] = u'baz'
        c1.save()

        c2 = self.mkcontact()
        c2.extra['foo'] = u'lorem'
        c2.extra['bar'] = u'ipsum'
        c2.save()

        response = self.client.post(reverse('contacts:people'), {
            '_export': True,
            'contact': [c1.key, c2.key],
        })

        self.assertContains(
            response,
            "The export is scheduled and should complete within a few"
            " minutes.")

        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(email.recipients(), [self.user_email])
        self.assertTrue('Contacts export' in email.subject)
        self.assertTrue('2 contact(s)' in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        [header, c1_data, c2_data, _] = csv_contents.split('\r\n')

        self.assertEqual(
            header,
            ','.join([
                'key', 'name', 'surname', 'email_address', 'msisdn', 'dob',
                'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
                'mxit_id', 'wechat_id', 'created_at', 'bar',
                'foo']))

        self.assertTrue(c1_data.startswith(c1.key))
        self.assertTrue(c1_data.endswith('baz,bar'))
        self.assertTrue(c2_data.startswith(c2.key))
        self.assertTrue(c2_data.endswith('ipsum,lorem'))
        self.assertTrue(contents)
        self.assertEqual(mime_type, 'application/zip')

    def test_contact_exporting_too_many(self):
        """
        If we have too many contacts to export, we only export a subset.
        """
        self.vumi_helper.patch_settings(CONTACT_EXPORT_TASK_LIMIT=2)

        c1 = self.mkcontact()
        c1.extra['foo'] = u'bar'
        c1.save()

        c2 = self.mkcontact()
        c2.extra['foo'] = u'baz'
        c2.save()

        c3 = self.mkcontact()
        c3.extra['foo'] = u'quux'
        c3.save()

        response = self.client.post(reverse('contacts:people'), {
            '_export': True,
            'contact': [c1.key, c2.key, c3.key],
        })

        self.assertContains(
            response,
            "The export is scheduled and should complete within a few"
            " minutes.")

        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(email.recipients(), [self.user_email])
        self.assertTrue('Contacts export' in email.subject)
        self.assertTrue(
            'NOTE: There are too many contacts to export.' in email.body)
        self.assertTrue('2 (out of 3) contacts' in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        [header, c1_data, c2_data, _] = csv_contents.split('\r\n')

        self.assertEqual(
            header,
            ','.join([
                'key', 'name', 'surname', 'email_address', 'msisdn', 'dob',
                'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
                'mxit_id', 'wechat_id', 'created_at', 'foo']))

        self.assertTrue(c1_data.startswith(c1.key))
        self.assertTrue(c1_data.endswith(',bar'))
        self.assertTrue(c2_data.startswith(c2.key))
        self.assertTrue(c2_data.endswith(',baz'))
        self.assertTrue(contents)
        self.assertEqual(mime_type, 'application/zip')

    def test_exporting_all_contacts(self):
        c1 = self.mkcontact()
        c1.extra['foo'] = u'bar'
        c1.extra['bar'] = u'baz'
        c1.save()

        c2 = self.mkcontact()
        c2.extra['foo'] = u'lorem'
        c2.extra['bar'] = u'ipsum'
        c2.save()

        response = self.client.post(reverse('contacts:people'), {
            '_export_all': True,
        })

        self.assertContains(
            response,
            "The export is scheduled and should complete within a few"
            " minutes.")

        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(email.recipients(), [self.user_email])
        self.assertTrue('Contacts export' in email.subject)
        self.assertTrue('2 contact(s)' in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        [header, c1_data, c2_data, _] = csv_contents.split('\r\n')

        self.assertEqual(
            header,
            ','.join([
                'key', 'name', 'surname', 'email_address', 'msisdn', 'dob',
                'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
                'mxit_id', 'wechat_id', 'created_at', 'bar',
                'foo']))

        self.assertTrue(c1_data.startswith(c1.key))
        self.assertTrue(c1_data.endswith('baz,bar'))
        self.assertTrue(c2_data.startswith(c2.key))
        self.assertTrue(c2_data.endswith('ipsum,lorem'))
        self.assertTrue(contents)
        self.assertEqual(mime_type, 'application/zip')

    def specify_columns(self, group_key, columns=None, import_rule=None,
                        follow=False):
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
        if import_rule is not None:
            defaults['import_rule'] = import_rule
        return self.client.post(group_url, defaults, follow=follow)

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
        self.assert_group_contacts_count(group, 0)

        response = self.specify_columns(group.key)
        self.assertRedirects(response, group_url(group.key))
        self.assert_group_contacts_count(group, 3)
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
        self.assert_group_contacts_count(group, 0)
        response = self.specify_columns(group.key)
        self.assertRedirects(response, group_url(group.key))
        self.assert_group_contacts_count(group, 3)
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

        response = self.specify_columns(group.key)
        self.assertRedirects(response, group_url(group.key))
        group = self.contact_store.get_group(group.key)
        self.assert_group_contacts_count(group, 3)
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

        response = self.specify_columns(group.key, columns={
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
        self.assertRedirects(response, group_url(group.key))
        group = self.contact_store.get_group(group.key)
        self.assert_group_contacts_count(group, 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_uploading_single_colum(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
                                  'fixtures',
                                  'sample-single-column-contacts.csv'))

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group.key,
            'file': csv_file,
        })
        self.assertRedirects(response, group_url(group.key))

        response = self.specify_columns(group.key, columns={
            'column-0': 'msisdn',
            'normalize-0': '',
        })
        self.assertRedirects(response, group_url(group.key))

        group = self.contact_store.get_group(group.key)
        self.assert_group_contacts_count(group, 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('successfully' in mail.outbox[0].subject)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_upload_with_contact_uuid(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
                                  'fixtures',
                                  'sample-contacts-with-uuid-headers.csv'))

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group.key,
            'file': csv_file,
        })
        self.assertRedirects(response, group_url(group.key))
        preview_response = self.client.get(group_url(group.key))
        self.assertContains(
            preview_response, 'The file includes contact UUIDs.')

    def test_upload_without_contact_uuid(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
                                  'fixtures',
                                  'sample-contacts-with-headers.csv'))

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group.key,
            'file': csv_file,
        })
        self.assertRedirects(response, group_url(group.key))
        preview_response = self.client.get(group_url(group.key))
        self.assertContains(
            preview_response, 'The file does not include contact UUIDs.')

    def create_temp_csv_file(self):
        return tempfile.NamedTemporaryFile(delete=False, suffix='.csv')

    def create_csv(self, fieldnames, data):
        fp = self.create_temp_csv_file()
        csv_writer = csv.DictWriter(fp, fieldnames=fieldnames)
        csv_writer.writerow(dict(zip(fieldnames, fieldnames)))
        for row in data:
            csv_writer.writerow(row)
        fp.seek(0)
        return fp

    def test_import_upload_is_truth(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)

        # create existing contacts that'll be updated.
        contact_data = []
        for i in range(3):
            # the original contact
            contact = self.mkcontact(name='', surname='', msisdn='270000000')
            # Litmus to ensure we don't butcher stuff
            contact.extra['litmus_stay'] = u'red'
            contact.extra['litmus_overwrite'] = u'blue'
            contact.subscription['sub'] = u'the-subscription'
            contact.dob = datetime(2014, 1, 2)
            contact.save()
            # what we're going to update
            contact_data.append({
                u'created_at': '2014-01-0%dT00:00:00' % (i + 1,),
                u'key': contact.key,
                u'name': u'name %s' % (i,),
                u'surname': u'surname %s' % (i,),
                u'msisdn': u'271111111%s' % (i,),
                u'litmus_new': u'green',
                u'litmus_overwrite': u'purple',
            })

        csv = self.create_csv(
            ['key', 'created_at', 'name', 'surname', 'msisdn',
             'litmus_overwrite', 'litmus_new'],
            contact_data)

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group.key,
            'file': csv,
        })

        self.assertRedirects(response, group_url(group.key))
        response = self.specify_columns(group.key, columns={
            'column-0': 'key',
            'column-1': 'created_at',
            'column-2': 'name',
            'column-3': 'surname',
            'column-4': 'msisdn',
            'column-5': 'litmus_overwrite',
            'column-6': 'litmus_new',
            'normalize-0': '',
            'normalize-1': '',
            'normalize-2': '',
            'normalize-3': '',
            'normalize-4': 'msisdn_za',
            'normalize-5': '',
            'normalize-6': '',
        }, import_rule='upload_is_truth')
        self.assertRedirects(response, group_url(group.key))

        group = self.contact_store.get_group(group.key)
        self.assert_group_contacts_count(group, 3)
        [email] = mail.outbox

        self.assertEqual('Contact import completed.', email.subject)
        self.assertTrue(
            "We've successfully imported 3 of your contact(s)" in email.body)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

        updated_contacts = [
            self.contact_store.get_contact_by_key(contact['key'])
            for contact in contact_data]
        self.assertEqual(
            set([contact.created_at for contact in updated_contacts]),
            set([datetime(2014, 1, 1),
                 datetime(2014, 1, 2),
                 datetime(2014, 1, 3)]))
        self.assertEqual(
            set([contact.name for contact in updated_contacts]),
            set(['name 0', 'name 1', 'name 2']))
        self.assertEqual(
            set([contact.surname for contact in updated_contacts]),
            set(['surname 0', 'surname 1', 'surname 2']))
        # these are normalized for ZA
        self.assertEqual(
            set([contact.msisdn for contact in updated_contacts]),
            set(['+2711111110', '+2711111111', '+2711111112']))

        # check the litmus
        self.assertEqual(
            set([contact.extra['litmus_stay']
                 for contact in updated_contacts]),
            set(['red']))
        self.assertEqual(
            set([contact.extra['litmus_new']
                 for contact in updated_contacts]),
            set(['green']))
        self.assertEqual(
            set([contact.extra['litmus_overwrite']
                 for contact in updated_contacts]),
            set(['purple']))
        self.assertEqual(
            set([contact.dob for contact in updated_contacts]),
            set([datetime(2014, 1, 2)]))
        self.assertEqual(
            set([contact.subscription['sub']
                 for contact in updated_contacts]),
            set(['the-subscription']))

        for contact in updated_contacts:
            self.assertEqual(
                set(contact.extra.keys()),
                set(['litmus_stay', 'litmus_new', 'litmus_overwrite']))

        os.unlink(csv.name)

    def test_import_existing_is_truth(self):
        group1 = self.contact_store.new_group(TEST_GROUP_NAME)
        group2 = self.contact_store.new_group(TEST_GROUP_NAME + ' 2')

        # create existing contacts that'll be updated.
        contact_data = []
        for i in range(3):
            # the original contact
            contact = self.mkcontact(
                name='foo', surname='bar', msisdn='270000000')
            # Litmus to ensure we don't butcher stuff
            contact.extra['litmus_stay'] = u'red'
            contact.subscription['sub'] = u'the-subscription'
            contact.created_at = datetime(2014, 1, i + 1)
            contact.dob = datetime(2014, 1, 2)
            contact.add_to_group(group2)
            contact.save()
            # what we're going to update
            contact_data.append({
                u'created_at': datetime(1970, 1, 1),
                u'key': contact.key,
                u'name': u'name %s' % (i,),
                u'surname': u'surname %s' % (i,),
                u'msisdn': u'271111111%s' % (i,),
                u'litmus_stay': u'green',
                u'litmus_new': u'blue',
            })

        csv = self.create_csv(
            ['key', 'created_at', 'name', 'surname', 'msisdn',
             'litmus_stay', 'litmus_new'],
            contact_data)

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group1.key,
            'file': csv,
        })

        self.assertRedirects(response, group_url(group1.key))
        response = self.specify_columns(group1.key, columns={
            'column-0': 'key',
            'column-1': 'created_at',
            'column-2': 'name',
            'column-3': 'surname',
            'column-4': 'msisdn',
            'column-5': 'litmus_stay',
            'column-6': 'litmus_new',
            'normalize-0': '',
            'normalize-1': '',
            'normalize-2': '',
            'normalize-3': '',
            'normalize-4': 'msisdn_za',
            'normalize-5': '',
            'normalize-6': '',
        }, import_rule='existing_is_truth')
        self.assertRedirects(response, group_url(group1.key))

        group = self.contact_store.get_group(group1.key)
        self.assert_group_contacts_count(group, 3)
        [email] = mail.outbox

        self.assertEqual('Contact import completed.', email.subject)
        self.assertTrue(
            "We've successfully imported 3 of your contact(s)" in email.body)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

        updated_contacts = [
            self.contact_store.get_contact_by_key(contact['key'])
            for contact in contact_data]
        self.assertEqual(
            set([contact.created_at for contact in updated_contacts]),
            set([datetime(2014, 1, 1),
                 datetime(2014, 1, 2),
                 datetime(2014, 1, 3)]))
        self.assertEqual(
            set([contact.name for contact in updated_contacts]),
            set(['foo']))
        self.assertEqual(
            set([contact.surname for contact in updated_contacts]),
            set(['bar']))
        # these are normalized for ZA
        self.assertEqual(
            set([contact.msisdn for contact in updated_contacts]),
            set(['270000000']))
        # check the litmus
        self.assertEqual(
            set([contact.extra['litmus_stay']
                 for contact in updated_contacts]),
            set(['red']))
        self.assertEqual(
            set([contact.extra['litmus_new']
                 for contact in updated_contacts]),
            set(['blue']))
        self.assertEqual(
            set([contact.dob for contact in updated_contacts]),
            set([datetime(2014, 1, 2)]))
        self.assertEqual(
            set([contact.dob for contact in updated_contacts]),
            set([datetime(2014, 1, 2)]))
        self.assertEqual(
            set([contact.subscription['sub']
                 for contact in updated_contacts]),
            set(['the-subscription']))

        for contact in updated_contacts:
            self.assertEqual(
                set(contact.extra.keys()),
                set(['litmus_stay', 'litmus_new']))

        groups = []
        for contact in updated_contacts:
            groups.extend(contact.groups.keys())

        self.assertEqual(
            set(groups),
            set([group1.key, group2.key]))

        os.unlink(csv.name)

    def test_import_existing_is_truth_fail_on_empty_key(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)

        # create existing contacts that'll be updated.
        contact_data = []
        contacts = []
        for i in range(3):
            # the original contact
            contact = self.mkcontact(
                name='foo', surname='bar', msisdn='270000000')
            # what we're going to update
            contacts.append(contact)
            contact_data.append({
                u'key': contact.key,
                u'twitter_handle': u'tweetor%d' % (i,),
            })

        # add a bad key
        contact_data[1]['key'] = ''

        csv = self.create_csv(['key', 'twitter_handle'], contact_data)

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group.key,
            'file': csv,
        })

        self.assertRedirects(response, group_url(group.key))
        response = self.specify_columns(group.key, columns={
            'column-0': 'key',
            'column-1': 'twitter_handle',
            'normalize-0': '',
            'normalize-1': '',
        }, import_rule='existing_is_truth')
        self.assertRedirects(response, group_url(group.key))

        [email] = mail.outbox

        self.assertEqual('Contact import completed.', email.subject)
        self.assertTrue(
            "We've successfully imported 2 of your contact(s)" in email.body)
        self.assertTrue(
            "Unfortunately there were also 1 errors. These are listed below:"
            in email.body)
        self.assertTrue(
            "row 2: No key provided" in email.body)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

        new_contact = self.contact_store.get_contact_by_key(contacts[0].key)
        self.assertEqual(new_contact.twitter_handle, 'tweetor0')
        self.assertEqual(new_contact.groups.keys(), [group.key])

        new_contact = self.contact_store.get_contact_by_key(contacts[1].key)
        self.assertEqual(new_contact.twitter_handle, None)
        self.assertEqual(new_contact.groups.keys(), [])

        new_contact = self.contact_store.get_contact_by_key(contacts[2].key)
        self.assertEqual(new_contact.twitter_handle, 'tweetor2')
        self.assertEqual(new_contact.groups.keys(), [group.key])

        os.unlink(csv.name)

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
        response = self.specify_columns(group_key=group.key)
        self.assertRedirects(response, group_url(group.key))
        self.assert_group_contacts_count(group, 3)
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
        self.assert_group_contacts_count(group, 0)

        # Now submit the column names and check that things have been written
        # to the db
        response = self.specify_columns(group.key)
        # Check the redirect
        self.assertRedirects(response, group_url)
        # 3 records should have been written to the db.
        self.assert_group_contacts_count(group, 3)
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
        }, follow=True)
        self.assertContains(response, "Something is wrong with the file")
        self.assertNotContains(response, "contact_data_headers")

    def test_contact_parsing_failure_bad_delimiter(self):
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
                        'fixtures', 'sample-contacts-bad-delimiter.csv'))
        response = self.client.post(reverse('contacts:people'), {
            'name': 'broken contacts group',
            'file': csv_file,
        }, follow=True)
        group = newest(self.contact_store.list_groups())
        self.assertRedirects(response, group_url(group.key))
        # We only get one column here.
        self.assertContains(response, 'column-0')
        self.assertNotContains(response, 'column-1')
        # Now we follow the response and check that we fail sensibly by
        # reporting that we don't have the expected fields.
        response = self.specify_columns(group_key=group.key, columns={
            'column-0': 'name',
            'normalize-0': '',
        }, follow=True)
        self.assertRedirects(response, group_url(group.key))

        messages = [(m.tags, m.message) for m in response.context['messages']]
        self.assertEqual(messages, [
            ("error", "Please specify a Contact Number field."),
        ])

        group = newest(self.contact_store.list_groups())
        self.assert_group_contacts_count(group, 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(default_storage.listdir("tmp"), ([], []))

    def test_contact_parsing_failure_no_msisdn_field(self):
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
                        'fixtures', 'sample-contacts.csv'))
        response = self.client.post(reverse('contacts:people'), {
            'name': 'broken contacts group',
            'file': csv_file,
        }, follow=True)
        group = newest(self.contact_store.list_groups())
        self.assertRedirects(response, group_url(group.key))

        # Here we don't specify an msisdn field, so that we explode in
        # the next bit.
        response = self.specify_columns(group_key=group.key, columns={
            'column-0': 'name',
            'column-1': 'surname',
            'column-2': 'accidental_extra',
            'normalize-0': '',
            'normalize-1': '',
            'normalize-2': '',
        }, follow=True)
        self.assertRedirects(response, group_url(group.key))

        messages = [(m.tags, m.message) for m in response.context['messages']]
        self.assertEqual(messages, [
            ("error", "Please specify a Contact Number field."),
        ])

        group = newest(self.contact_store.list_groups())
        self.assert_group_contacts_count(group, 0)
        self.assertEqual(len(mail.outbox), 0)
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
        contacts = self.get_all_contacts(self.get_group_contact_keys(group))

        self.assertTrue(all([contact.msisdn == '+27761234561' for contact in
                        contacts]))
        self.assertTrue(all([contact.extra['integer'] == '2' for contact in
                        contacts]))
        self.assertTrue(all([contact.extra['float'] == '2.0' for contact in
                        contacts]))

    def test_contact_querying(self):
        contact = self.mkcontact()
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
        contact = self.mkcontact()
        people_url = reverse('contacts:people')
        self.client.get(people_url, {
            'q': 'name:%s' % (contact.name,)
        })


class TestGroups(BaseContactsTestCase):
    def get_all_contacts(self, keys=None):
        if keys is None:
            keys = self.contact_store.list_contacts()
        contacts = []
        for batch in self.contact_store.contacts.load_all_bunches(keys):
            contacts.extend(batch)
        return contacts

    def get_latest_contact(self):
        return max(self.get_all_contacts(), key=lambda c: c.created_at)

    def list_group_keys(self):
        return [group.key for group in self.contact_store.list_groups()]

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
        contact = self.mkcontact(groups=[group])
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

        for i in range(10):
            self.mkcontact(groups=[group])

        default_limit = self.client.get(group_url(group.key), {
            'q': TEST_CONTACT_NAME,
        })

        self.assertContains(
            default_limit,
            escape("Showing 10 of the group's 10 contact(s)"))

        custom_limit = self.client.get(group_url(group.key), {
            'q': TEST_CONTACT_NAME,
            'limit': 5,
        })
        self.assertContains(
            custom_limit,
            escape("Showing 5 of the group's 10 contact(s)"))

    def test_multiple_group_deletion(self):
        group_1 = self.contact_store.new_group(TEST_GROUP_NAME)
        group_2 = self.contact_store.new_group(TEST_GROUP_NAME)

        # Delete the groups
        groups_url = reverse('contacts:groups')
        response = self.client.post(groups_url, {
            'group': [group_1.key, group_2.key],
            '_delete': True,
        })
        self.assertRedirects(response, groups_url)
        self.assertEqual(self.contact_store.list_groups(), [])

    def test_removing_contacts_from_group(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        c1 = self.mkcontact(groups=[group])
        c2 = self.mkcontact(groups=[group])

        group_url = reverse('contacts:group', kwargs={'group_key': group.key})
        response = self.client.post(group_url, {
            '_remove': True,
            'contact': [c1.key]
        })
        self.assertRedirects(response, group_url)

        self.assertEqual(
            [c2.key],
            get_all_contact_keys_for_group(self.contact_store, group))

    def test_group_empty_post(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)

        self.assertEqual(self.list_group_keys(), [group.key])
        group_url = reverse('contacts:group', kwargs={'group_key': group.key})
        response = self.client.post(group_url)
        self.assertRedirects(response, group_url)

        self.assertEqual(self.list_group_keys(), [group.key])

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
            [], get_all_contact_keys_for_group(self.contact_store, group))
        self.assertFalse(contact in self.contact_store.list_contacts())

    def test_group_contact_export(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        contact = self.mkcontact(groups=[group])
        # Clear the group
        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key,
        })

        # add some extra info to ensure it gets exported properly
        contact.extra['foo'] = u'bar'
        contact.extra['bar'] = u'baz'
        contact.save()

        response = self.client.post(group_url, {'_export': True})

        self.assertRedirects(response, group_url)
        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(email.recipients(), [self.user_email])
        self.assertTrue(
            '%s contacts export' % (group.name,) in email.subject)
        self.assertTrue(
            '1 contact(s) from group "%s" attached' % (group.name,)
            in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        [header, csv_contact, _] = csv_contents.split('\r\n')

        self.assertEqual(
            header,
            ','.join([
                'key', 'name', 'surname', 'email_address', 'msisdn', 'dob',
                'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
                'mxit_id', 'wechat_id', 'created_at', 'bar',
                'foo']))

        self.assertTrue(csv_contact.startswith(contact.key))
        self.assertTrue(csv_contact.endswith('baz,bar'))
        self.assertTrue(contents)
        self.assertEqual(mime_type, 'application/zip')

    def test_group_contact_export_with_prefix(self):
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        contact = self.mkcontact(groups=[group])
        # Clear the group
        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key,
        })

        # add some extra info to ensure it gets exported properly
        contact.extra['msisdn'] = u'bar'
        contact.extra['name'] = u'baz'
        contact.save()

        response = self.client.post(group_url, {'_export': True})

        self.assertRedirects(response, group_url)
        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(email.recipients(), [self.user_email])
        self.assertTrue(
            '%s contacts export' % (group.name,) in email.subject)
        self.assertTrue(
            '1 contact(s) from group "%s" attached' % (group.name,)
            in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        [header, csv_contact, _] = csv_contents.split('\r\n')
        self.assertEqual(
            header,
            ','.join([
                'key', 'name', 'surname', 'email_address', 'msisdn', 'dob',
                'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
                'mxit_id', 'wechat_id', 'created_at', 'extras-msisdn',
                'extras-name']))

        self.assertTrue(csv_contact.startswith(contact.key))
        self.assertTrue(csv_contact.endswith('bar,baz'))
        self.assertTrue(contents)
        self.assertEqual(mime_type, 'application/zip')

    def test_multiple_group_exportation(self):
        group_1 = self.contact_store.new_group(u'Test Group 1')
        contact_1 = self.mkcontact(groups=[group_1])
        contact_1.extra['foo'] = u'bar'
        contact_1.extra['bar'] = u'baz'
        contact_1.save()

        group_2 = self.contact_store.new_group(u'Test Group 2')
        contact_2 = self.mkcontact(groups=[group_2])
        contact_2.extra['foo'] = u'lorem'
        contact_2.extra['bar'] = u'ipsum'
        contact_2.save()

        groups_url = reverse('contacts:groups')
        self.client.post(groups_url, {
            'group': [group_1.key, group_2.key],
            '_export': True,
        })

        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(email.recipients(), [self.user_email])
        self.assertTrue('Contacts export' in email.subject)
        self.assertTrue(
            '2 contact(s) from the following groups:',
            '\n  - Test Group 1'
            '\n  - Test Group 2'
            in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        [header, c1_data, c2_data, _] = csv_contents.split('\r\n')

        self.assertEqual(
            header,
            ','.join([
                'key', 'name', 'surname', 'email_address', 'msisdn', 'dob',
                'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
                'mxit_id', 'wechat_id', 'created_at', 'bar',
                'foo']))

        self.assertTrue(c1_data.startswith(contact_1.key))
        self.assertTrue(c1_data.endswith('baz,bar'))
        self.assertTrue(c2_data.startswith(contact_2.key))
        self.assertTrue(c2_data.endswith('ipsum,lorem'))
        self.assertTrue(contents)
        self.assertEqual(mime_type, 'application/zip')


class TestSmartGroups(BaseContactsTestCase):
    def mksmart_group(self, query, name='a smart group'):
        response = self.client.post(reverse('contacts:groups'), {
            'name': name,
            'query': query,
            '_new_smart_group': '1',
        })
        group = newest(self.contact_store.list_groups())
        self.assertRedirects(response, group_url(group.key))
        return group

    def list_group_keys(self):
        return [group.key for group in self.contact_store.list_groups()]

    def add_to_group(self, contact, group):
        contact.add_to_group(group)
        contact.save()
        return contact

    def test_smart_groups_creation(self):
        group = self.mksmart_group('msisdn:\+12*')
        self.assertEqual(u'a smart group', group.name)
        self.assertEqual(u'msisdn:\+12*', group.query)

    def test_smart_group_empty_post(self):
        group = self.mksmart_group('msisdn:\+12*')
        group_url = reverse('contacts:group', kwargs={'group_key': group.key})
        response = self.client.post(group_url)
        self.assertRedirects(response, group_url)
        self.assertEqual(self.list_group_keys(), [group.key])

    def test_smart_group_deletion(self):
        group = self.mksmart_group('msisdn:\+12*')
        self.assertEqual(self.list_group_keys(), [group.key])
        group_url = reverse('contacts:group', kwargs={'group_key': group.key})
        response = self.client.post(group_url, {'_delete_group': 1})
        self.assertRedirects(response, reverse('contacts:index'),
                             target_status_code=302)
        self.assertEqual(self.list_group_keys(), [])

    def test_smart_group_clearing(self):
        contact = self.mkcontact()
        group = self.mksmart_group('msisdn:\+12*')
        self.assertEqual(
            [contact.key],
            get_all_contact_keys_for_group(self.contact_store, group))
        response = self.client.post(
            reverse('contacts:group', kwargs={'group_key': group.key}),
            {'_delete_group_contacts': 1})
        self.assertRedirects(response, reverse('contacts:group', kwargs={
            'group_key': group.key}))
        self.assertEqual(
            [], get_all_contact_keys_for_group(self.contact_store, group))

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
        conversation = self.user_helper.create_conversation(u'bulk_message')
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
        conversation = self.user_helper.create_conversation(u'bulk_message')
        conversation.groups.add(group)
        conversation.save()

        self.assertRedirects(response, group_url(group.key))
        self.assertEqual(u'a smart group', group.name)
        self.assertEqual(u'msisdn:\+12*', group.query)
        self.assertEqual(
            list(self.contact_store.get_static_contact_keys_for_group(group)),
            [])
        self.assertEqual(
            list(self.contact_store.get_dynamic_contact_keys_for_group(group)),
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
        conversation = self.user_helper.create_conversation(u'bulk_message')
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
        conv = self.user_helper.create_conversation(u'bulk_message')
        conv.groups.add(group)
        conv.save()

        self.assertEqual(
            set(self.contact_store.get_contacts_for_conversation(conv)),
            set([contact1.key, contact2.key, contact3.key]))

    def test_smart_group_limit(self):
        for i in range(10):
            self.mkcontact(name=u'Ben')

        self.client.post(reverse('contacts:groups'), {
            'name': 'a smart group',
            'query': 'name:Ben',
            '_new_smart_group': '1',
        })
        group = newest(self.contact_store.list_groups())

        default_limit = self.client.get('%s?query=Ben' % (
            reverse('contacts:group', kwargs={
                'group_key': group.key,
            }),))
        self.assertContains(
            default_limit,
            escape("Showing 10 of the group's 10 contact(s)"))

        custom_limit = self.client.get('%s?query=Ben&limit=5' % (
            reverse('contacts:group', kwargs={
                'group_key': group.key,
            }),))
        self.assertContains(
            custom_limit,
            escape("Showing 5 of the group's 10 contact(s)"))

    def test_smartgroup_contact_export(self):
        self.client.post(reverse('contacts:groups'), {
            'name': 'a smart group',
            'query': 'name:foo OR surname:bar',
            '_new_smart_group': '1',
        })

        self.mkcontact(surname='bar')
        self.mkcontact(name='foo')
        self.mkcontact(name='foo', surname='bar')

        group = newest(self.contact_store.list_groups())
        group_url = reverse('contacts:group', kwargs={
            'group_key': group.key,
        })
        self.assertEqual(group.name, 'a smart group')
        response = self.client.post(group_url, {'_export': True})

        contacts = get_all_contact_keys_for_group(self.contact_store, group)
        self.assertEqual(len(contacts), 3)

        self.assertRedirects(response, group_url)
        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(file_name, 'contacts-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('contacts-export.csv', 'r').read()

        self.assertEqual(email.recipients(), [self.user_email])
        self.assertTrue(
            '%s contacts export' % (group.name,) in email.subject)
        self.assertTrue(
            '%s contact(s) from group "%s" attached' % (
                len(contacts), group.name) in email.body)
        self.assertEqual(file_name, 'contacts-export.zip')
        self.assertTrue(csv_contents)
        self.assertEqual(mime_type, 'application/zip')


class TestFieldNormalizer(GoDjangoTestCase):

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
