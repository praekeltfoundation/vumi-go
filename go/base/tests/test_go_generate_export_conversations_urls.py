# -*- coding: utf-8 -*-
from StringIO import StringIO

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.base.management.commands import go_generate_export_conversations_urls
# from go.vumitools.tests.helpers import GoMessageHelper


class TestGoGenExportConvUrls(GoDjangoTestCase):

    base_url = 'http://localhost:1234/export/'

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user_email = self.user_helper.get_django_user().email

        self.command = go_generate_export_conversations_urls.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_direction(self):
        conv = self.user_helper.create_conversation(u"http_api")
        self.command.handle(email=self.user_email,
                            base_url=self.base_url,
                            template=self.command.DEFAULT_TEMPLATE)
        output = self.command.stdout.getvalue()
        self.assertTrue('inbound' in output)
        self.assertTrue('outbound' in output)
        self.assertTrue(conv.batch.key in output)

    def test_running(self):
        self.user_helper.create_conversation(u"http_api", started=True)
        self.command.handle(email=self.user_email,
                            base_url=self.base_url,
                            template=self.command.DEFAULT_TEMPLATE)
        output = self.command.stdout.getvalue()
        self.assertTrue('running' in output)

    def test_stopped(self):
        conv = self.user_helper.create_conversation(u"http_api")
        conv.stop_conversation()
        self.command.handle(email=self.user_email,
                            base_url=self.base_url,
                            template=self.command.DEFAULT_TEMPLATE)
        output = self.command.stdout.getvalue()
        self.assertTrue('stopping' in output)

    def test_archived(self):
        conv = self.user_helper.create_conversation(u"http_api")
        conv.archive_conversation()
        self.command.handle(email=self.user_email,
                            base_url=self.base_url,
                            template=self.command.DEFAULT_TEMPLATE)
        output = self.command.stdout.getvalue()
        self.assertTrue('archived' in output)

    def test_template(self):
        self.user_helper.create_conversation(u"http_api")
        self.command.handle(email=self.user_email,
                            base_url='http://foo/bar/',
                            template='Hello {direction} {status}\n')
        output = self.command.stdout.getvalue()
        self.assertEqual(
            output, 'Hello inbound stopped\nHello outbound stopped\n')
