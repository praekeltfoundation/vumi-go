from StringIO import StringIO

from go.base.management.commands import go_manage_routing_table
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.vumitools.routing_table import GoConnector


class TestGoManageRoutingTableCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

        self.command = go_manage_routing_table.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def assert_routing_entries(self, routing_table, expected_entries):
        self.assertEqual(
            sorted(routing_table.entries()),
            sorted((GoConnector.parse(str(sc)), se,
                    GoConnector.parse(str(dc)), de)
                   for sc, se, dc, de in expected_entries))

    def handle_command(self, **options):
        user_email = self.user_helper.get_django_user().email
        options.setdefault('email_address', user_email)
        options.setdefault('show', False)
        options.setdefault('clear', False)
        options.setdefault('add', ())
        options.setdefault('remove', ())
        self.command.handle(**options)
        return (self.command.stdout.getvalue().strip().split('\n'),
                self.command.stderr.getvalue().strip().split('\n'))

    def test_show_empty(self):
        outlines, errlines = self.handle_command(show=True)
        self.assertEqual(['The routing table is empty.'], outlines)
        self.assertEqual([''], errlines)

    def test_show_not_empty(self):
        user_account = self.user_helper.get_user_account()
        rt = user_account.routing_table
        tag_conn = 'TRANSPORT_TAG:new:tag1'
        conv_conn = 'CONVERSATION:new:12345'
        rt.add_entry(tag_conn, "default", conv_conn, "default")
        rt.add_entry(conv_conn, "default", tag_conn, "default")
        user_account.save()

        outlines, errlines = self.handle_command(show=True)
        self.assertEqual([
            'Routing table:',
            '  CONVERSATION:new:12345',
            '      default  ->  TRANSPORT_TAG:new:tag1 - default',
            '  TRANSPORT_TAG:new:tag1',
            '      default  ->  CONVERSATION:new:12345 - default',
        ], outlines)
        self.assertEqual([''], errlines)

    def test_clear(self):
        user_account = self.user_helper.get_user_account()
        rt = user_account.routing_table
        tag_conn = 'TRANSPORT_TAG:new:tag1'
        conv_conn = 'CONVERSATION:new:12345'
        rt.add_entry(tag_conn, "default", conv_conn, "default")
        rt.add_entry(conv_conn, "default", tag_conn, "default")
        user_account.save()

        self.assertTrue(self.user_helper.user_api.get_routing_table())
        outlines, errlines = self.handle_command(clear=True)
        self.assertEqual(['Routing table cleared.'], outlines)
        self.assertEqual([''], errlines)
        self.assertFalse(self.user_helper.user_api.get_routing_table())

    def test_add(self):
        conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'active')
        account = self.user_helper.get_user_account()
        account.tags.append(('new', 'tag1'))
        account.save()
        tag_conn = 'TRANSPORT_TAG:new:tag1'
        conv_conn = 'CONVERSATION:%s:%s' % (conv.conversation_type, conv.key)

        self.assertFalse(self.user_helper.user_api.get_routing_table())
        outlines, errlines = self.handle_command(
            add=(tag_conn, "default", conv_conn, "default"))
        self.assertEqual(['Routing table entry added.'], outlines)
        self.assertEqual([''], errlines)
        self.assert_routing_entries(
            self.user_helper.user_api.get_routing_table(),
            [(tag_conn, "default", conv_conn, "default")])

    def test_remove(self):
        conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'active')
        account = self.user_helper.get_user_account()
        account.tags.append(('new', 'tag1'))
        tag_conn = 'TRANSPORT_TAG:new:tag1'
        conv_conn = 'CONVERSATION:%s:%s' % (conv.conversation_type, conv.key)
        rt = account.routing_table
        rt.add_entry(tag_conn, "default", conv_conn, "default")
        rt.add_entry(conv_conn, "default", tag_conn, "default")
        account.save()

        self.assertTrue(self.user_helper.user_api.get_routing_table())
        outlines, errlines = self.handle_command(
            remove=(tag_conn, "default", conv_conn, "default"))
        self.assertEqual(['Routing table entry removed.'], outlines)
        self.assertEqual([''], errlines)
        self.assert_routing_entries(
            self.user_helper.user_api.get_routing_table(),
            [(conv_conn, "default", tag_conn, "default")])
