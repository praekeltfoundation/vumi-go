from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import (
        GoDjangoTestCase, DjangoVumiApiHelper, CommandIO)
    from go.base.management.commands import (
        go_generate_export_conversations_urls)
    from django.core.management import call_command

    Command = go_generate_export_conversations_urls.Command


class TestGoGenExportConvUrls(GoDjangoTestCase):

    base_url = 'http://localhost:1234/export/'

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user_email = self.user_helper.get_django_user().email

    def run_command(self, **kw):
        cmd_io = CommandIO()
        call_command('go_generate_export_conversations_urls',
                     stdout=cmd_io.stdout, stderr=cmd_io.stderr, **kw)
        return cmd_io

    def test_direction(self):
        conv = self.user_helper.create_conversation(u"http_api")
        cmd = self.run_command(
            email=self.user_email,
            base_url=self.base_url,
            template=Command.DEFAULT_TEMPLATE)
        output = cmd.stdout.getvalue()
        self.assertTrue('inbound' in output)
        self.assertTrue('outbound' in output)
        self.assertTrue(conv.batch.key in output)

    def test_running(self):
        self.user_helper.create_conversation(u"http_api", started=True)
        cmd = self.run_command(
            email=self.user_email,
            base_url=self.base_url,
            template=Command.DEFAULT_TEMPLATE)
        output = cmd.stdout.getvalue()
        self.assertTrue('running' in output)

    def test_stopped(self):
        conv = self.user_helper.create_conversation(u"http_api")
        conv.stop_conversation()
        cmd = self.run_command(
            email=self.user_email,
            base_url=self.base_url,
            template=Command.DEFAULT_TEMPLATE)
        output = cmd.stdout.getvalue()
        self.assertTrue('stopping' in output)

    def test_archived(self):
        conv = self.user_helper.create_conversation(u"http_api")
        conv.archive_conversation()
        cmd = self.run_command(
            email=self.user_email,
            base_url=self.base_url,
            template=Command.DEFAULT_TEMPLATE)
        output = cmd.stdout.getvalue()
        self.assertTrue('archived' in output)

    def test_template(self):
        self.user_helper.create_conversation(u"http_api")
        cmd = self.run_command(
            email=self.user_email,
            base_url=self.base_url,
            template='Hello {direction} {status}\n')
        output = cmd.stdout.getvalue()
        self.assertEqual(
            output, 'Hello inbound stopped\nHello outbound stopped\n')
