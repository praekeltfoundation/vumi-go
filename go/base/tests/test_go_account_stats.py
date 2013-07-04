# -*- coding: utf-8 -*-
from StringIO import StringIO
from datetime import datetime

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_account_stats


class GoAccountStatsCommandTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(GoAccountStatsCommandTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()

        self.command = go_account_stats.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_command_summary(self):
        self.command.handle()
        output = self.command.stdout.getvalue().split('\n')
        self.assertEqual(output[0], 'Known commands:')
        self.assertEqual(output[1], 'list_conversations:')

    def test_list_conversations(self):
        active_conv = self.create_conversation(name=u'active')
        inactive_conv = self.create_conversation(name=u'inactive')
        inactive_conv.archive_conversation()

        self.command.handle(self.django_user.username, 'list_conversations')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 2)
        self.assertTrue(active_conv.key in output[0])
        self.assertTrue(inactive_conv.key in output[1])

    def test_list_conversations_with_unicode(self):
        self.create_conversation(name=u'active')
        unicode_conv = self.create_conversation(name=u'Zoë destroyer of Ascii')
        self.command.handle(self.django_user.username, 'list_conversations')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 2)
        self.assertTrue(unicode_conv.key in output[1])
        self.assertTrue('Zo\xc3\xab' in output[1])

    def test_list_conversations_active(self):
        active_conv = self.create_conversation(name=u'active')
        inactive_conv = self.create_conversation(name=u'inactive')
        inactive_conv.archive_conversation()
        self.command.handle(
            self.django_user.username, 'list_conversations', 'active')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 1)
        self.assertTrue(active_conv.key in output[0])

    def test_stats(self):
        conv = self.create_conversation(started=True, name=u'active')
        self.put_sample_messages_in_conversation(
            5, conv, reply=True, time_multiplier=0)

        self.command.handle(self.django_user.username, 'stats', conv.key)
        output = self.command.stdout.getvalue().strip().split('\n')
        [batch_key] = conv.batches.keys()
        self.assertEqual(output, [
            u'Conversation: active',
            u'Total Received in batch %s: 5' % (batch_key,),
            u'Total Sent in batch %s: 5' % (batch_key,),
            u'Total Uniques: 5',
            u'Received per date:',
            u'%s: 5' % (datetime.now().date(),),
            u'Sent per date:',
            u'%s: 5' % (datetime.now().date(),),
        ])
