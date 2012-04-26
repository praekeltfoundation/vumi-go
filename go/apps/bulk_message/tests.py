from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings
from go.conversation.models import Conversation
from go.contacts.models import ContactGroup, Contact
from go.base.utils import padded_queryset
from go.base.tests.utils import override_settings
from vumi.tests.utils import FakeRedis
from vumi.message import TransportUserMessage
from go.vumitools.tests.utils import CeleryTestMixIn, VumiApiCommand
from datetime import datetime
from os import path


def reload_record(record):
    return record.__class__.objects.get(pk=record.pk)


class BulkMessageTestCase(TestCase, CeleryTestMixIn):

    fixtures = ['test_user', 'test_conversation',
                    'test_group', 'test_contact']

    def setUp(self):
        self.setup_api()
        self.declare_longcode_tags()
        self.setup_celery_for_tests()

        self.client = Client()
        self.client.login(username='username', password='password')

        self.user = User.objects.get(username='username')
        self.conversation = self.user.conversation_set.latest()

    def tearDown(self):
        self.teardown_api()

    def setup_api(self):
        self._fake_redis = FakeRedis()
        self._old_vumi_api_config = settings.VUMI_API_CONFIG
        settings.VUMI_API_CONFIG = {
            'redis_cls': lambda **kws: self._fake_redis,
            'message_store': {},
            'message_sender': {},
            }

    def teardown_api(self):
        settings.VUMI_API_CONFIG = self._old_vumi_api_config
        self._fake_redis.teardown()

    def declare_longcode_tags(self):
        api = Conversation.vumi_api()
        api.declare_tags([("longcode", "default%s" % i) for i
                          in range(10001, 10001 + 4)])

    def acquire_all_longcode_tags(self):
        api = Conversation.vumi_api()
        for _i in range(4):
            api.acquire_tag("longcode")

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        # render the form
        self.assertEqual(Conversation.objects.count(), 1)
        response = self.client.get(reverse('bulk_message:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('bulk_message:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
            'delivery_class': 'sms',
            'delivery_tag_pool': 'longcode',
        })
        self.assertEqual(Conversation.objects.count(), 2)
        conversation = Conversation.objects.latest()
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, 'longcode')
        self.assertRedirects(response, reverse('bulk_message:people', kwargs={
            'conversation_pk': conversation.pk,
        }))

    def test_end(self):
        """
        Test ending the conversation
        """
        self.assertFalse(self.conversation.ended())
        response = self.client.post(reverse('bulk_message:end', kwargs={
            'conversation_pk': self.conversation.pk}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_pk': self.conversation.pk}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation ended")
        self.conversation = reload_record(self.conversation)
        self.assertTrue(self.conversation.ended())

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        response = self.client.post(reverse('bulk_message:people',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'groups': [grp.pk for grp in ContactGroup.objects.all()],
            'delivery_class': 'shortcode',
        })
        self.assertRedirects(response, reverse('bulk_message:send', kwargs={
            'conversation_pk': self.conversation.pk}))

    def test_send(self):
        """
        Test the start conversation view
        """
        consumer = self.get_cmd_consumer()
        # print 'consumer', consumer

        response = self.client.post(reverse('bulk_message:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_pk': self.conversation.pk}))

        [cmd] = self.fetch_cmds(consumer)
        [batch] = self.conversation.message_batch_set.all()
        [contact] = self.conversation.people()
        conversation = self.conversation
        msg_options = {"from_addr": "default10001",
                       "transport_type": "sms",
                       "transport_name": "smpp_transport",
                       "worker_name": "bulk_message_application",
                       "conversation_id": conversation.pk,
                       "conversation_type": conversation.conversation_type,
                       }
        self.assertEqual(cmd, VumiApiCommand.send(batch.batch_id,
                                                  "Test message",
                                                  msg_options,
                                                  contact.msisdn))

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        self.acquire_all_longcode_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('bulk_message:send', kwargs={
            'conversation_pk': self.conversation.pk}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        [] = self.fetch_cmds(consumer)
        [] = self.conversation.preview_batch_set.all()
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_pk': self.conversation.pk}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.subject, 'Test Conversation')

