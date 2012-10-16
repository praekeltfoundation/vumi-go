# -*- coding: utf-8 -*-
from StringIO import StringIO
from datetime import datetime

from django.contrib.auth.models import User

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_account_stats
from go.base.utils import vumi_api_for_user


class GoAccountStatsCommandTestCase(VumiGoDjangoTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoAccountStatsCommandTestCase, self).setUp()
        self.user = User.objects.create(username='test@user.com',
            first_name='Test', last_name='User', password='password',
            email='test@user.com')

        self.api = vumi_api_for_user(self.user)

        def mkconv(*args, **kwargs):
            return self.api.wrap_conversation(
                self.api.conversation_store.new_conversation(*args, **kwargs))

        self.active_conv = mkconv(u'bulk_message', u'active', u'content')
        self.inactive_conv = mkconv(u'bulk_message', u'inactive', u'content',
            end_timestamp=datetime.now())
        self.unicode_conv = mkconv(u'bulk_message', u'Zoë destroyer of Ascii',
            u'content', end_timestamp=datetime.now())
        self.assertTrue(self.inactive_conv.ended())

        self.command = go_account_stats.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_command_summary(self):
        self.command.handle()
        output = self.command.stdout.getvalue().split('\n')
        self.assertEqual(output[0], 'Known commands:')
        self.assertEqual(output[1], 'list_conversations:')

    def test_list_conversations(self):
        self.command.handle('test@user.com', 'list_conversations')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 3)
        self.assertTrue(self.active_conv.key in output[0])
        self.assertTrue(self.inactive_conv.key in output[1])

    def test_list_conversations_with_unicode(self):
        self.command.handle('test@user.com', 'list_conversations')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 3)
        self.assertTrue(self.unicode_conv.key in output[2])
        self.assertTrue('Zo\xc3\xab' in output[2])

    def test_list_conversations_active(self):
        self.command.handle('test@user.com', 'list_conversations', 'active')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 1)
        self.assertTrue(self.active_conv.key in output[0])

    def test_stats(self):
        self.command.handle('test@user.com', 'stats', self.active_conv.key)
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(output, [
            u'Conversation: active',
            u'Total Received: 0',
            u'Total Sent: 0',
            u'Total Uniques: 0',
            u'Received per date:',
            u'Sent per date:',
        ])
