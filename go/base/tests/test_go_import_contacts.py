import os.path
from cStringIO import StringIO

from django.conf import settings

from go.base.management.commands import go_import_contacts
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoImportContactsCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.contact_store = self.user_helper.user_api.contact_store

        self.command = go_import_contacts.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()
        self.vumi_helper.setup_tagpool(u"pool", [u"tag1", u"tag2"])

    def invoke_command(self, **kw):
        options = {
            'email_address': self.user_helper.get_django_user().email,
            'contacts_csv': os.path.join(
                settings.PROJECT_ROOT, 'base', 'fixtures',
                'sample-contacts-with-headers.csv'),
            'groups': [],
        }
        options.update(kw)
        self.command.handle(**options)
        return self.command.stdout.getvalue()

    def assert_contacts_count(self, count):
        contacts = self.contact_store.list_contacts()
        self.assertEqual(len(contacts), count)

    def assert_group_contacts_count(self, group, count):
        contact_keys = []
        contact_keys_page = group.backlinks.contact_keys()
        while contact_keys_page is not None:
            contact_keys.extend(contact_keys_page)
            contact_keys_page = contact_keys_page.next_page()
        self.assertEqual(len(contact_keys), count)

    def test_import_no_groups(self):
        self.assert_contacts_count(0)
        self.invoke_command()
        self.assert_contacts_count(3)

    def test_import_one_group(self):
        group = self.contact_store.new_group(u'test group')
        self.assert_contacts_count(0)
        self.assert_group_contacts_count(group, 0)
        self.invoke_command(groups=[group.key])
        self.assert_contacts_count(3)
        self.assert_group_contacts_count(group, 3)

    def test_import_two_groups(self):
        group1 = self.contact_store.new_group(u'test group 1')
        group2 = self.contact_store.new_group(u'test group 1')
        self.assert_contacts_count(0)
        self.assert_group_contacts_count(group1, 0)
        self.assert_group_contacts_count(group2, 0)
        self.invoke_command(groups=[group1.key, group2.key])
        self.assert_contacts_count(3)
        self.assert_group_contacts_count(group1, 3)
        self.assert_group_contacts_count(group2, 3)
