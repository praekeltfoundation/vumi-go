import os.path
from cStringIO import StringIO

from django.conf import settings

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_import_contacts
from go.base.utils import vumi_api_for_user


class GoImportContactsCommandTestCase(VumiGoDjangoTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoImportContactsCommandTestCase, self).setUp()
        self.setup_api()
        self.user = self.mk_django_user()
        self.user_api = vumi_api_for_user(self.user)
        self.profile = self.user.get_profile()

    def invoke_command(self, **kw):
        options = {
            'email-address': self.user.username,
            'contacts-csv': os.path.join(
                settings.PROJECT_ROOT, 'base', 'fixtures',
                'sample-contacts-with-headers.csv'),
            'groups': [],
        }
        options.update(kw)
        command = go_import_contacts.Command()
        command.stdout = StringIO()
        command.handle(**options)
        return command.stdout.getvalue()

    def assert_contacts_count(self, count):
        contacts = self.user_api.contact_store.list_contacts()
        self.assertEqual(len(contacts), count)

    def test_import_no_groups(self):
        self.assert_contacts_count(0)
        self.invoke_command()
        self.assert_contacts_count(3)

    def test_import_one_group(self):
        group = self.user_api.contact_store.new_group(u'test group')
        self.assert_contacts_count(0)
        self.assertEqual(len(group.backlinks.contacts()), 0)
        self.invoke_command(groups=[group.key])
        self.assert_contacts_count(3)
        self.assertEqual(len(group.backlinks.contacts()), 3)

    def test_import_two_groups(self):
        group1 = self.user_api.contact_store.new_group(u'test group 1')
        group2 = self.user_api.contact_store.new_group(u'test group 1')
        self.assert_contacts_count(0)
        self.assertEqual(len(group1.backlinks.contacts()), 0)
        self.assertEqual(len(group2.backlinks.contacts()), 0)
        self.invoke_command(groups=[group1.key, group2.key])
        self.assert_contacts_count(3)
        self.assertEqual(len(group1.backlinks.contacts()), 3)
        self.assertEqual(len(group2.backlinks.contacts()), 3)
