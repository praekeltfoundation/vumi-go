from datetime import date

from django.test.client import Client
from django.core import mail
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site

from go.vumitools.tests.utils import VumiApiCommand
from go.vumitools.token_manager import TokenManager
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.tests.utils import FakeMessageStoreClient, FakeMatchResult

from mock import patch


class BulkMessageTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'bulk_message'

    def setUp(self):
        super(BulkMessageTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def run_new_conversation(self, selected_option, pool, tag):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('bulk_message:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('bulk_message:new'), {
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
        self.assertRedirects(response, reverse('bulk_message:people', kwargs={
            'conversation_key': conversation.key,
        }))

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        self.run_new_conversation('longcode:', 'longcode', None)

    def test_new_conversation_with_user_selected_tags(self):
        tp_meta = self.api.tpm.get_metadata('longcode')
        tp_meta['user_selects_tag'] = True
        self.api.tpm.set_metadata(u'longcode', tp_meta)
        self.run_new_conversation(u'longcode:default10001', u'longcode',
                                  u'default10001')

    def test_end(self):
        """
        Test ending the conversation
        """
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.ended())
        response = self.client.post(reverse('bulk_message:end', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_key': conversation.key}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation ended")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.ended())

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        response = self.client.post(reverse('bulk_message:people',
            kwargs={'conversation_key': self.conv_key}), {'groups': [
                    grp.key for grp in self.contact_store.list_groups()]})
        self.assertRedirects(response, reverse('bulk_message:start', kwargs={
            'conversation_key': self.conv_key}))

    def test_start(self):
        """
        Test the start conversation view
        """
        conversation = self.get_wrapped_conv()

        response = self.client.post(reverse('bulk_message:start', kwargs={
            'conversation_key': conversation.key}))
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_key': conversation.key}))

        conversation = self.get_wrapped_conv()
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

        [cmd] = self.get_api_commands_sent()
        expected_cmd = VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            batch_id=batch.key,
            dedupe=False,
            msg_options=msg_options,
            conversation_type=conversation.conversation_type,
            conversation_key=conversation.key,
            is_client_initiated=conversation.is_client_initiated(),
            )
        self.assertEqual(cmd, expected_cmd)

    def test_start_with_deduplication(self):
        conversation = self.get_wrapped_conv()
        self.client.post(
            reverse('bulk_message:start', kwargs={
                    'conversation_key': conversation.key}),
            {'dedupe': '1'})
        [cmd] = self.get_api_commands_sent()
        self.assertEqual(cmd.payload['kwargs']['dedupe'], True)

    def test_start_without_deduplication(self):
        conversation = self.get_wrapped_conv()
        self.client.post(reverse('bulk_message:start', kwargs={
            'conversation_key': conversation.key}), {
        })
        [cmd] = self.get_api_commands_sent()
        self.assertEqual(cmd.payload['kwargs']['dedupe'], False)

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        conversation = self.get_wrapped_conv()
        self.acquire_all_longcode_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('bulk_message:start', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:start', kwargs={
            'conversation_key': conversation.key}))
        [] = self.fetch_cmds(consumer)
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.subject, self.TEST_SUBJECT)

    def test_show_cached_message_pagination(self):
        # Create 21 inbound & 21 outbound messages, since we have
        # 20 messages per page it should give us 2 pages
        self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 21)
        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key}))

        # Check pagination
        # We should have 60 references to a contact, which by default display
        # the from_addr if a contact cannot be found. (each block as 3
        # references, one in the table listing, 2 in the reply-to modal div)
        self.assertContains(response, 'from-', 60)
        # We should have 2 links to page to, one for the actual page link
        # and one for the 'Next' page link
        self.assertContains(response, '&amp;p=2', 2)
        # There should only be 1 link to the current page
        self.assertContains(response, '&amp;p=1', 1)
        # There should not be a link to the previous page since we are not
        # the first page.
        self.assertContains(response, '&amp;p=0', 0)

    def test_show_cached_message_overview(self):
        self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 10)
        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key
            }))
        self.assertContains(response,
            '10 sent for delivery to the networks.')
        self.assertContains(response,
            '10 accepted for delivery by the networks.')
        self.assertContains(response, '10 delivered.')

    @patch('go.base.message_store_client.MatchResult')
    @patch('go.base.message_store_client.Client')
    def test_message_search(self, Client, MatchResult):
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult()
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        response = self.client.get(reverse('bulk_message:show', kwargs={
                'conversation_key': self.conv_key,
            }), {
                'q': 'hello world 1',
            })

        template_names = [t.name for t in response.templates]
        self.assertTrue('generic/includes/message-load-results.html' in
                        template_names)
        self.assertEqual(response.context['token'], fake_client.token)

    @patch('go.base.message_store_client.MatchResult')
    @patch('go.base.message_store_client.Client')
    def test_message_results(self, Client, MatchResult):
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult(tries=2,
            results=[self.mkmsg_out() for i in range(10)])
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        fetch_results_url = reverse('bulk_message:message_search_result',
            kwargs={
                'conversation_key': self.conv_key,
            })
        fetch_results_params = {
            'q': 'hello world 1',
            'batch_id': 'batch-id',
            'direction': 'inbound',
            'token': fake_client.token,
            'delay': 100,
        }

        response1 = self.client.get(fetch_results_url,
                                    fetch_results_params)
        response2 = self.client.get(fetch_results_url,
                                    fetch_results_params)

        # First time it should still show the loading page
        self.assertTrue('generic/includes/message-load-results.html' in
                            [t.name for t in response1.templates])
        self.assertEqual(response1.context['delay'], 1.1 * 100)
        # Second time it should still render the messages
        self.assertTrue('generic/includes/message-list.html' in
                            [t.name for t in response2.templates])
        self.assertEqual(response1.context['token'], fake_client.token)
        # Second time we should list the matching messages
        self.assertEqual(response2.context['token'], fake_client.token)
        self.assertEqual(len(response2.context['message_page'].object_list),
            10)

    def test_aggregates(self):
        self.put_sample_messages_in_conversation(self.user_api,
            self.conv_key, 10, start_timestamp=date(2012, 1, 1),
            time_multiplier=12)
        response = self.client.get(reverse('bulk_message:aggregates', kwargs={
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
        self.put_sample_messages_in_conversation(self.user_api,
            self.conv_key, 10, start_timestamp=date(2012, 1, 1),
            time_multiplier=12)
        conv_url = reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key,
            })
        response = self.client.post(conv_url, {
            '_export_conversation_messages': True,
            })
        self.assertRedirects(response, conv_url)
        [email] = mail.outbox
        self.assertEqual(email.recipients(), [self.user.email])
        self.assertTrue(self.conversation.subject in email.subject)
        self.assertTrue(self.conversation.subject in email.body)
        [(file_name, content, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.csv')
        # 1 header, 10 sent, 10 received, 1 trailing newline == 22
        self.assertEqual(22, len(content.split('\n')))
        self.assertEqual(mime_type, 'text/csv')


class ConfirmBulkMessageTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'bulk_message'

    def setUp(self):
        super(ConfirmBulkMessageTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')
        self.redis = self.get_redis_manager()
        self.tm = TokenManager(self.redis.sub_manager('token_manager'))

    def test_confirm_start_conversation_get(self):
        """
        Test the start conversation view with the confirm_start_conversation
        enabled for the account's profile.
        """
        profile = self.user.get_profile()
        account = profile.get_user_account()
        account.confirm_start_conversation = True
        account.save()

        conversation = self.user_api.get_wrapped_conversation(self.conv_key)

        response = self.client.get(reverse('bulk_message:start', kwargs={
            'conversation_key': conversation.key
            }))

        self.assertEqual(response.context['confirm_start_conversation'], True)
        template_names = [t.name for t in response.templates]
        self.assertTrue('generic/includes/conversation_start_confirmation.html'
                            in template_names)

    def test_confirm_start_conversation_post(self):
        """
        Test the start conversation view with the confirm_start_conversation
        enabled for the account's profile.

        A POST to this should send out the confirmation message, not the full
        bulk send.
        """

        profile = self.user.get_profile()
        account = profile.get_user_account()
        account.msisdn = u'+27761234567'
        account.confirm_start_conversation = True
        account.save()

        conversation = self.user_api.get_wrapped_conversation(self.conv_key)

        # mock the token generation
        with patch.object(TokenManager, 'generate_token') as mock_method:
            mock_method.return_value = ('abcdef', '123456')
            response = self.client.post(reverse('bulk_message:start', kwargs={
                'conversation_key': conversation.key,
                }))

        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_key': conversation.key,
            }))

        conversation = self.user_api.get_wrapped_conversation(self.conv_key)
        [batch] = conversation.get_batches()
        [tag] = list(batch.tags)
        [contact] = self.get_contacts_for_conversation(conversation)
        msg_options = {
            "transport_type": "sms",
            "transport_name": self.transport_name,
            "from_addr": "default10001",
            "helper_metadata": {
                "tag": {
                    "tag": list(tag)
                },
                "go": {
                    "user_account": conversation.user_account.key,
                    "sensitive": True,
                },
            },
        }

        [cmd] = self.get_api_commands_sent()
        site = Site.objects.get_current()
        expected_cmd = VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_message',
            command_data={
                'batch_id': batch.key,
                'msg_options': msg_options,
                'content':
                    'Please visit http://%s%s to start your conversation.' % (
                    site.domain, reverse('token', kwargs={'token': 'abcdef'})),
                'to_addr': account.msisdn,
            }
        )
        self.assertEqual(cmd, expected_cmd)

    def test_confirmation_get(self):
        conversation = self.user_api.get_wrapped_conversation(self.conv_key)
        token = self.tm.generate('/foo/', user_id=self.user.pk)
        token_data = self.tm.get(token)
        full_token = '%s-%s%s' % (len(token), token,
                                    token_data['system_token'])

        response = self.client.get('%s?token=%s' % (
            reverse('bulk_message:confirm', kwargs={
                'conversation_key': conversation.key,
            }), full_token))

        self.assertContains(response, conversation.subject)
        self.assertContains(response, conversation.message)

    def test_confirmation_post(self):
        conversation = self.user_api.get_wrapped_conversation(self.conv_key)

        # we're faking this here, this would normally have happened when
        # the confirmation SMS was sent out.
        tag = conversation.acquire_tag()
        # store manually so that when we acquire_existing_tag() later we get
        # the one already used, not another random one from the same pool.
        conversation.c.delivery_tag = unicode(tag[1])
        batch_key = conversation.start_batch(tag)
        conversation.batches.add_key(batch_key)
        conversation.save()

        token = self.tm.generate('/foo/', user_id=self.user.pk, extra_params={
            'dedupe': True,
            })
        token_data = self.tm.get(token)
        full_token = '%s-%s%s' % (len(token), token,
                                    token_data['system_token'])

        response = self.client.post(reverse('bulk_message:confirm', kwargs={
            'conversation_key': conversation.key,
            }), {
                'token': full_token,
            })

        self.assertContains(response, conversation.subject)
        self.assertContains(response, conversation.message)
        self.assertContains(response, "Conversation confirmed")
        self.assertContains(response, "Conversation started succesfully!")

        # reload the conversation because batches are cached.
        conversation = self.user_api.get_wrapped_conversation(conversation.key)
        # ugly hack because grabbing the latest batch key here is tricky
        # because we `get_latest_batch_key()` depends on the cache being
        # populated which at this point it isn't yet.
        batch_keys = conversation.get_batch_keys()
        self.assertEqual(len(batch_keys), 1)
        self.assertEqual([batch_key], batch_keys)

        batch = conversation.mdb.get_batch(batch_key)
        [tag] = list(batch.tags)
        [cmd] = self.get_api_commands_sent()

        msg_options = {
            "transport_type": "sms",
            "transport_name": self.transport_name,
            "from_addr": "default10001",
            "helper_metadata": {
                "tag": {"tag": list(tag)},
                "go": {"user_account": conversation.user_account.key},
                },
            }

        expected_cmd = VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            batch_id=batch.key,
            dedupe=True,
            msg_options=msg_options,
            conversation_type=conversation.conversation_type,
            conversation_key=conversation.key,
            is_client_initiated=conversation.is_client_initiated(),
            )

        self.assertEqual(cmd, expected_cmd)

        # check token was consumed so it can't be re-used to send the
        # conversation messages again
        self.assertEqual(self.tm.get(token), None)

        # check repost fails because token has been deleted
        response = self.client.post(reverse('bulk_message:confirm', kwargs={
            'conversation_key': conversation.key,
            }), {
                'token': full_token,
            })
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.tm.get(token), None)


class SendOneOffReplyTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(SendOneOffReplyTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def test_actions_on_inbound_only(self):
        messages = self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 1)
        [msg_in, msg_out, ack, dr] = messages[0]

        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key
            }), {'direction': 'inbound'})
        self.assertContains(response, 'Reply')
        self.assertContains(response, 'href="#reply-%s"' % (
            msg_in['message_id'],))

        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key
            }), {'direction': 'outbound'})
        self.assertNotContains(response, 'Reply')

    def test_send_one_off_reply(self):
        self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 1)
        conversation = self.get_wrapped_conv()
        [msg] = conversation.received_messages()
        response = self.client.post(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key
            }), {
                'in_reply_to': msg['message_id'],
                'content': 'foo',
                'to_addr': 'should be ignored',
                '_send_one_off_reply': True,
            })
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key,
            }))

        [start_cmd, reply_to_cmd] = self.get_api_commands_sent()
        [tag] = conversation.get_tags()
        msg_options = conversation.make_message_options(tag)
        msg_options['in_reply_to'] = msg['message_id']
        self.assertEqual(reply_to_cmd['worker_name'],
                            'bulk_message_application')
        self.assertEqual(reply_to_cmd['command'], 'send_message')
        self.assertEqual(reply_to_cmd['kwargs']['command_data'], {
            'batch_id': conversation.get_latest_batch_key(),
            'conversation_key': conversation.key,
            'content': 'foo',
            'to_addr': msg['from_addr'],
            'msg_options': msg_options,
            })
