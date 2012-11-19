# -*- coding: utf-8 -*-
from uuid import uuid4
from StringIO import StringIO
from datetime import datetime

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.management.commands import go_account_stats


class GoAccountStatsCommandTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(GoAccountStatsCommandTestCase, self).setUp()
        self.user = self.mk_django_user()
        self.setup_user_api(self.user)

        self.message_store = self.api.mdb

        self.active_conv = self.mkstartedconv(name=u'active')

        [batch_key] = self.active_conv.batches.keys()
        for i in range(10):
            msg = self.mkmsg_in(message_id=uuid4().hex, to_addr='shortcode',
                from_addr='from-%s' % (i,))
            self.message_store.add_inbound_message(msg, batch_id=batch_key)
            self.message_store.add_outbound_message(msg.reply('thanks'),
                batch_id=batch_key)

        self.inactive_conv = self.mkstartedconv(name=u'inactive')
        self.inactive_conv.end_conversation()
        self.assertTrue(self.inactive_conv.ended())

        self.unicode_conv = self.mkstartedconv(name=u'Zoë destroyer of Ascii')
        self.unicode_conv.end_conversation()
        self.assertTrue(self.unicode_conv.ended())

        self.command = go_account_stats.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def mkstartedconv(self, **kwargs):
        kwargs.update({
            u'delivery_class': u'sms',
            u'delivery_tag_pool': u'longcode',
            })
        conv = self.user_api.wrap_conversation(self.mkconversation(**kwargs))
        conv.start()
        return conv

    def test_command_summary(self):
        self.command.handle()
        output = self.command.stdout.getvalue().split('\n')
        self.assertEqual(output[0], 'Known commands:')
        self.assertEqual(output[1], 'list_conversations:')

    def test_list_conversations(self):
        self.command.handle(self.user.username, 'list_conversations')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 3)
        self.assertTrue(self.active_conv.key in output[0])
        self.assertTrue(self.inactive_conv.key in output[1])

    def test_list_conversations_with_unicode(self):
        self.command.handle(self.user.username, 'list_conversations')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 3)
        self.assertTrue(self.unicode_conv.key in output[2])
        self.assertTrue('Zo\xc3\xab' in output[2])

    def test_list_conversations_active(self):
        self.command.handle(self.user.username, 'list_conversations', 'active')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 1)
        self.assertTrue(self.active_conv.key in output[0])

    def test_stats(self):
        self.command.handle(self.user.username, 'stats', self.active_conv.key)
        output = self.command.stdout.getvalue().strip().split('\n')
        [batch_key] = self.active_conv.batches.keys()
        self.assertEqual(output, [
            u'Conversation: active',
            u'Total Received in batch %s: 10' % (batch_key,),
            u'Total Sent in batch %s: 10' % (batch_key,),
            u'Total Uniques: 10',
            u'Received per date:',
            u'%s: 10' % (datetime.now().date(),),
            u'Sent per date:',
            u'%s: 10' % (datetime.now().date(),),
        ])
