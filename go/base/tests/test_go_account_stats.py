# -*- coding: utf-8 -*-
from StringIO import StringIO
from datetime import datetime

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.base.management.commands import go_account_stats
from go.vumitools.tests.helpers import GoMessageHelper


class TestGoAccountStatsCommand(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user_email = self.user_helper.get_django_user().email

        self.command = go_account_stats.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_command_summary(self):
        self.command.handle()
        output = self.command.stdout.getvalue().split('\n')
        self.assertEqual(output[0], 'Known commands:')
        self.assertEqual(output[1], 'list_conversations:')

    def test_list_conversations(self):
        active_conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'active')
        inactive_conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'inactive')
        inactive_conv.archive_conversation()

        self.command.handle(self.user_email, 'list_conversations')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 2)
        self.assertTrue(active_conv.key in output[0])
        self.assertTrue(inactive_conv.key in output[1])

    def test_list_conversations_with_unicode(self):
        self.user_helper.create_conversation(u'bulk_message', name=u'active')
        unicode_conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'Zoë destroyer of Ascii')
        self.command.handle(self.user_email, 'list_conversations')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 2)
        self.assertTrue(unicode_conv.key in output[1])
        self.assertTrue('Zo\xc3\xab' in output[1])

    def test_list_conversations_active(self):
        active_conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'active')
        inactive_conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'inactive')
        inactive_conv.archive_conversation()
        self.command.handle(
            self.user_email, 'list_conversations', 'active')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 1)
        self.assertTrue(active_conv.key in output[0])

    def test_stats(self):
        msg_helper = GoMessageHelper(vumi_helper=self.vumi_helper)
        conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'active', started=True)
        start_date = datetime(
            2015, 1, 1, 11, 10, 9, microsecond=0)
        msgs = msg_helper.add_inbound_to_conv(
            conv, 5, start_date=start_date, time_multiplier=0)
        msg_helper.add_replies_to_conv(conv, msgs)
        # Add one more inbound message so sent != received.
        msg_helper.add_inbound_to_conv(
            conv, 1, start_date=start_date, time_multiplier=0)

        self.command.handle(self.user_email, 'stats', conv.key)
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(output, [
            u'Conversation: active',
            u'Total Received in batch %s: 6' % (conv.batch.key,),
            u'Total Sent in batch %s: 5' % (conv.batch.key,),
            u'Total Uniques: 5',
            u'Received per date:',
            u'%s: 6' % (start_date.date(),),
            u'Sent per date:',
            u'%s: 5' % (start_date.date(),),
        ])

    def test_stats_with_microsecond_timestamps(self):
        msg_helper = GoMessageHelper(vumi_helper=self.vumi_helper)
        conv = self.user_helper.create_conversation(
            u'bulk_message', name=u'active', started=True)
        start_date = datetime(
            2015, 1, 1, 11, 10, 9, microsecond=123)
        msgs = msg_helper.add_inbound_to_conv(
            conv, 5, start_date=start_date, time_multiplier=0)
        msg_helper.add_replies_to_conv(conv, msgs)
        # Add one more inbound message so sent != received.
        msg_helper.add_inbound_to_conv(
            conv, 1, start_date=start_date, time_multiplier=0)

        self.command.handle(self.user_email, 'stats', conv.key)
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(output, [
            u'Conversation: active',
            u'Total Received in batch %s: 6' % (conv.batch.key,),
            u'Total Sent in batch %s: 5' % (conv.batch.key,),
            u'Total Uniques: 5',
            u'Received per date:',
            u'%s: 6' % (start_date.date(),),
            u'Sent per date:',
            u'%s: 5' % (start_date.date(),),
        ])
