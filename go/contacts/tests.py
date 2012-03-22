from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from go.contacts.models import ContactGroup, Contact
from os import path
from django.conf import settings


class ContactsTestCase(TestCase):

    fixtures = ['test_user', 'test_group', 'test_contact']

    def setUp(self):
        self.client = Client()
        self.client.login(username='username', password='password')

    def tearDown(self):
        pass

    def test_redirect_index(self):
        response = self.client.get(reverse('contacts:index'))
        self.assertRedirects(response, reverse('contacts:groups'))

    def test_groups_creation(self):
        response = self.client.post(reverse('contacts:groups'), {
            'name': 'a new group',
        })
        group = ContactGroup.objects.latest()
        self.assertEqual(group.name, 'a new group')
        self.assertRedirects(response, reverse('contacts:group', kwargs={
            'group_pk': group.pk,
        }))

    def test_group_contact_querying(self):
        group = ContactGroup.objects.latest()
        group_url = reverse('contacts:group', kwargs={'group_pk': group.pk})
        contact = Contact.objects.latest()
        contact.groups.add(group)
        contact_url = reverse('contacts:person', kwargs={
            'person_pk': contact.pk})

        # test no-match
        response = self.client.get(group_url, {
            'q': contact.name + 'not matching',
        })
        self.assertContains(response, 'No contact match')

        # test match
        response = self.client.get(group_url, {
            'q': contact.name,
        })
        self.assertContains(response, contact_url)

    def test_group_contact_filter_by_letter(self):
        group = ContactGroup.objects.latest()
        group_url = reverse('contacts:group', kwargs={'group_pk': group.pk})
        contact = Contact.objects.latest()
        contact.groups.add(group)
        contact_url = reverse('contacts:person', kwargs={
            'person_pk': contact.pk})

        # assert the fixture doesn't load a contact with a surname starting
        # with a z
        contact_first_letter = contact.surname[0]
        self.assertNotEqual(contact_first_letter, 'z')
        response = self.client.get(group_url, {'l': 'z'})
        self.assertContains(response, 'No contact surnames start with '
                                        'the letter')
        response = self.client.get(group_url, {'l': contact_first_letter})
        self.assertContains(response, contact_url)

    def test_contact_creation(self):
        group = ContactGroup.objects.latest()
        response = self.client.post(reverse('contacts:new_person'), {
            'msisdn': '27761234567',
            'groups': [group.pk],
        })
        contact = Contact.objects.latest()
        self.assertRedirects(response, reverse('contacts:person', kwargs={
            'person_pk': contact.pk,
        }))

    def test_contact_update(self):
        contact = Contact.objects.latest()
        contact_url = reverse('contacts:person', kwargs={
            'person_pk': contact.pk,
        })
        response = self.client.post(contact_url, {
            'name': 'changed name',
            'surname': 'changed surname',
            'msisdn': '112',
            'groups': [cg.pk for cg in ContactGroup.objects.all()],
        })
        self.assertRedirects(response, contact_url)
        # reload to check
        contact = Contact.objects.get(pk=contact.pk)
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
        group = ContactGroup.objects.latest()
        group_url = reverse('contacts:group', kwargs={'group_pk': group.pk})
        self.assertRedirects(response, group_url)
        self.assertEqual(group.contact_set.count(), 3)  # nr of contacts in CSV

    def test_contact_upload_into_existing_group(self):
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-contacts.csv'))
        group = ContactGroup.objects.latest()
        group.contact_set.clear()
        group_url = reverse('contacts:group', kwargs={'group_pk': group.pk})

        response = self.client.post(reverse('contacts:people'), {
            'contact_group': group.pk,
            'file': csv_file,
        })
        self.assertRedirects(response, group_url)
        self.assertEqual(group.contact_set.count(), 3)  # nr of contacts in CSV

    def test_contact_upload_failure(self):
        response = self.client.post(reverse('contacts:people'), {
            'name': 'a new group',
            'file': None,
        })
        self.assertContains(response, 'Something went wrong with the upload')
        self.assertFalse(ContactGroup.objects.filter(name='a new group')\
            .exists())

    def test_contact_phone_number_normalization(self):
        settings.VUMI_COUNTRY_CODE = '27'
        csv_file = open(path.join(settings.PROJECT_ROOT, 'base',
            'fixtures', 'sample-denormalized-contacts.csv'))
        response = self.client.post(reverse('contacts:people'), {
            'name': 'normalization group',
            'file': csv_file,
        })
        group = ContactGroup.objects.latest()
        group_url = reverse('contacts:group', kwargs={'group_pk': group.pk})
        self.assertRedirects(response, group_url)
        self.assertTrue(all([c.msisdn.startswith('+27') for c
                                in group.contact_set.all()]))

    def test_contact_letter_filter(self):
        contact = Contact.objects.latest()
        contact_url = reverse('contacts:person', kwargs={
            'person_pk': contact.pk,
        })
        people_url = reverse('contacts:people')

        # assert the fixture doesn't load a contact with a surname starting
        # with a z
        contact_first_letter = contact.surname[0]
        self.assertNotEqual(contact_first_letter, 'z')
        response = self.client.get(people_url, {'l': 'z'})
        self.assertContains(response, 'No contact surnames start with '
                                        'the letter')
        response = self.client.get(people_url, {'l': contact_first_letter})
        self.assertContains(response, contact_url)

    def test_contact_querying(self):
        contact = Contact.objects.latest()
        contact_url = reverse('contacts:person', kwargs={
            'person_pk': contact.pk})
        people_url = reverse('contacts:people')

        # test no-match
        response = self.client.get(people_url, {
            'q': contact.name + 'not matching',
        })
        self.assertContains(response, 'No contact match')

        # test match
        response = self.client.get(people_url, {
            'q': contact.name,
        })
        self.assertContains(response, contact_url)
