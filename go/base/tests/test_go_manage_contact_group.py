from cStringIO import StringIO

from go.base.management.commands import go_manage_contact_group
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoManageContactGroupCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.contact_store = self.user_helper.user_api.contact_store
        self.command = go_manage_contact_group.Command()

    def invoke_command(self, command, **kw):
        options = {
            'email_address': self.user_helper.get_django_user().email,
            'command': [command]
        }
        options.update(kw)
        self.command.stdout = StringIO()
        self.command.handle(**options)
        return self.command.stdout.getvalue()

    def test_list_groups(self):
        output = self.invoke_command('list')
        self.assertEqual(output, 'No contact groups found.\n')

        group = self.contact_store.new_group(u'test group')
        output = self.invoke_command('list')
        self.assertEqual(output, ' * %s [%s] "test group"\n' % (
            group.key, group.created_at.strftime('%Y-%m-%d %H:%M')))

        sgroup = self.contact_store.new_smart_group(
            u'sg', query=u'foo')
        output = self.invoke_command('list')
        self.assertEqual(
            output, ' * %s [%s] "test group"\n * %s [%s] (smart) "sg"\n' % (
                group.key, group.created_at.strftime('%Y-%m-%d %H:%M'),
                sgroup.key, sgroup.created_at.strftime('%Y-%m-%d %H:%M'),
            ))

    def test_create_group(self):
        self.assertEqual([], self.user_helper.user_api.list_groups())
        output = self.invoke_command('create', group=u'new group')
        [group] = self.user_helper.user_api.list_groups()
        self.assertEqual(group.name, u'new group')
        lines = output.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'Group created:')
        self.assertTrue(group.key in lines[1])

    def test_create_smart_group(self):
        self.assertEqual([], self.user_helper.user_api.list_groups())
        output = self.invoke_command(
            'create_smart', group='smart group', query='foo')
        [group] = self.user_helper.user_api.list_groups()
        self.assertEqual(group.name, u'smart group')
        self.assertEqual(group.query, u'foo')
        lines = output.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'Group created:')
        self.assertTrue(group.key in lines[1])
        self.assertTrue('(smart)' in lines[1])

    def test_delete_empty_group(self):
        self.assertEqual([], self.user_helper.user_api.list_groups())
        group = self.contact_store.new_group(u'test group')
        [lgroup] = self.user_helper.user_api.list_groups()
        self.assertEqual(group.key, lgroup.key)
        output = self.invoke_command('delete', group=group.key)
        self.assertEqual([], self.user_helper.user_api.list_groups())
        lines = output.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], 'Deleting group:')
        self.assertTrue(group.key in lines[1])
        self.assertEqual(lines[2], '')
        self.assertEqual(lines[3], 'Done.')

    def test_delete_full_group(self):
        self.assertEqual([], self.user_helper.user_api.list_groups())
        group = self.contact_store.new_group(u'test group')
        self.contact_store.new_contact(msisdn=u'123', groups=[group])
        self.contact_store.new_contact(msisdn=u'456', groups=[group])
        [lgroup] = self.user_helper.user_api.list_groups()
        self.assertEqual(group.key, lgroup.key)
        output = self.invoke_command('delete', group=group.key)
        self.assertEqual([], self.user_helper.user_api.list_groups())
        lines = output.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], 'Deleting group:')
        self.assertTrue(group.key in lines[1])
        self.assertEqual(lines[2], '..')
        self.assertEqual(lines[3], 'Done.')
