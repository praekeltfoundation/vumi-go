from datetime import date
from zipfile import ZipFile
from StringIO import StringIO

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.core import mail

from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase


class MultiSurveyTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'multi_survey'

    def setUp(self):
        super(MultiSurveyTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')
        self.patch_settings(
            VXPOLLS_REDIS_CONFIG=self._persist_config['redis_manager'])

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def run_new_conversation(self, selected_option, pool, tag):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('multi_survey:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('multi_survey:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'delivery_class': 'sms',
            'delivery_tag_pool': selected_option,
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, pool)
        self.assertEqual(conversation.delivery_tag, tag)
        self.assertRedirects(response, reverse('multi_survey:surveys', kwargs={
                    'conversation_key': conversation.key,
                    }))

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        self.run_new_conversation('longcode:', 'longcode', None)

    def test_new_conversation_with_user_selected_tags(self):
        tp_meta = self.api.tpm.get_metadata('longcode')
        tp_meta['user_selects_tag'] = True
        self.api.tpm.set_metadata('longcode', tp_meta)
        self.run_new_conversation('longcode:default10001', 'longcode',
                                  'default10001')

    def test_end(self):
        """
        Test ending the conversation
        """
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.ended())
        response = self.client.post(reverse('multi_survey:end', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('multi_survey:show', kwargs={
            'conversation_key': conversation.key}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Survey ended")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.ended())

    def test_client_or_server_init_distinction(self):
        """A survey should not ask for recipients if the transport
        used only supports client initiated sessions (i.e. USSD)"""

        self.api.tpm.set_metadata("pool1", {
            "delivery_class": "sms",
            "server_initiated": True,
            })

        self.api.tpm.set_metadata("pool2", {
            "delivery_class": "ussd",
            "client_initiated": True,
            })

        def get_people_page(tag_pool):
            conversation = self.get_wrapped_conv()
            conversation.c.delivery_tag_pool = tag_pool
            conversation.save()
            return self.client.get(reverse('multi_survey:people', kwargs={
                'conversation_key': conversation.key,
                }))
        self.assertContains(get_people_page(u'pool1'), 'Survey Recipients')
        self.assertNotContains(get_people_page(u'pool2'), 'Survey Recipients')

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.is_client_initiated())
        response = self.client.post(reverse('multi_survey:people',
            kwargs={'conversation_key': conversation.key}), {'groups': [
                    grp.key for grp in self.contact_store.list_groups()]})
        self.assertRedirects(response, reverse('multi_survey:start', kwargs={
            'conversation_key': conversation.key}))

    def test_start(self):
        """
        Test the start conversation view
        """
        response = self.client.post(reverse('multi_survey:start', kwargs={
            'conversation_key': self.conv_key}))
        self.assertRedirects(response, reverse('multi_survey:show', kwargs={
            'conversation_key': self.conv_key}))

        conversation = self.get_wrapped_conv()
        [start_cmd, hack_cmd] = self.get_api_commands_sent()
        [batch] = conversation.get_batches()
        [tag] = list(batch.tags)
        [contact] = self.get_contacts_for_conversation(conversation)
        msg_options = {
            "transport_type": "sms",
            "transport_name": self.transport_name,
            "from_addr": "default10001",
            "helper_metadata": {
                "tag": {"tag": list(tag)},
                "go": {"user_account": conversation.user_account.key},
                },
            }

        self.assertEqual(start_cmd, VumiApiCommand.command(
                '%s_application' % (conversation.conversation_type,), 'start',
                user_account_key=conversation.user_account.key,
                conversation_key=conversation.key))
        self.assertEqual(hack_cmd, VumiApiCommand.command(
                '%s_application' % (conversation.conversation_type,),
                'initial_action_hack',
                user_account_key=conversation.user_account.key,
                conversation_key=conversation.key,
                is_client_initiated=conversation.is_client_initiated(),
                batch_id=batch.key, msg_options=msg_options))

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        self.acquire_all_longcode_tags()
        response = self.client.post(reverse('multi_survey:start', kwargs={
            'conversation_key': self.conv_key}), follow=True)
        self.assertRedirects(response, reverse('multi_survey:start', kwargs={
            'conversation_key': self.conv_key}))
        [] = self.get_api_commands_sent()
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('multi_survey:show', kwargs={
            'conversation_key': self.conv_key}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, 'Test Conversation')

    def test_aggregates(self):
        self.put_sample_messages_in_conversation(
            self.user_api, self.conv_key, 10, start_date=date(2012, 1, 1),
            time_multiplier=12)
        response = self.client.get(reverse('multi_survey:aggregates', kwargs={
            'conversation_key': self.conv_key
            }), {'direction': 'inbound'})
        self.assertEqual(response.content, '\r\n'.join([
            '2011-12-28,2',
            '2011-12-29,2',
            '2011-12-30,2',
            '2011-12-31,2',
            '2012-01-01,2',
            '',  # csv ends with a blank line
            ]))

    def test_export_messages(self):
        self.put_sample_messages_in_conversation(
            self.user_api, self.conv_key, 10, start_date=date(2012, 1, 1),
            time_multiplier=12)
        conv_url = reverse('multi_survey:show', kwargs={
            'conversation_key': self.conv_key,
            })
        response = self.client.post(conv_url, {
            '_export_conversation_messages': True,
            })
        self.assertRedirects(response, conv_url)
        [email] = mail.outbox
        self.assertEqual(email.recipients(), [self.user.email])
        self.assertTrue(self.conversation.name in email.subject)
        self.assertTrue(self.conversation.name in email.body)
        [(file_name, contents, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('messages-export.csv', 'r').read()

        # 1 header, 10 sent, 10 received, 1 trailing newline == 22
        self.assertEqual(22, len(csv_contents.split('\n')))
        self.assertEqual(mime_type, 'application/zip')

    def test_send_one_off_reply(self):
        self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 1)
        conversation = self.get_wrapped_conv()
        [msg] = conversation.received_messages()
        response = self.client.post(reverse('multi_survey:show', kwargs={
            'conversation_key': self.conv_key
            }), {
                'in_reply_to': msg['message_id'],
                'content': 'foo',
                'to_addr': 'should be ignored',
                '_send_one_off_reply': True,
            })
        self.assertRedirects(response, reverse('multi_survey:show', kwargs={
            'conversation_key': self.conv_key,
            }))

        [start_cmd, hack_cmd, reply_to_cmd] = self.get_api_commands_sent()
        [tag] = conversation.get_tags()
        msg_options = conversation.make_message_options(tag)
        msg_options['in_reply_to'] = msg['message_id']
        self.assertEqual(reply_to_cmd['worker_name'],
                            'multi_survey_application')
        self.assertEqual(reply_to_cmd['command'], 'send_message')
        self.assertEqual(reply_to_cmd['kwargs']['command_data'], {
            'batch_id': conversation.get_latest_batch_key(),
            'conversation_key': conversation.key,
            'content': 'foo',
            'to_addr': msg['from_addr'],
            'msg_options': msg_options,
            })
