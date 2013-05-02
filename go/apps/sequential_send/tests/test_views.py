from django.test.client import Client
from django.core.urlresolvers import reverse

from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.apps.sequential_send.views import SequentialSendConversationViews


# FIXME: These tests are probably broken.


class SequentialSendTestCase(DjangoGoApplicationTestCase):
    VIEWS_CLASS = SequentialSendConversationViews
    TEST_CONVERSATION_PARAMS = {'delivery_tag': u"default10001"}

    def setUp(self):
        super(SequentialSendTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def run_new_conversation(self, delivery_class, pool, tag):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        response = self.client.get(reverse('sequential_send:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('sequential_send:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'delivery_class': delivery_class,
            'delivery_tag_pool': '%s:%s' % (pool, tag),
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 3)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, pool)
        self.assertEqual(conversation.delivery_tag, tag)
        self.assertRedirects(
            response, reverse('sequential_send:edit', kwargs={
                    'conversation_key': conversation.key,
                    }))

    def test_new_conversation(self):
        parent = self.conv_store.new_conversation(
            conversation_type=u'bulk_message', subject=self.TEST_SUBJECT,
            message=u"Test message", delivery_class=u"sms",
            delivery_tag_pool=u"longcode", delivery_tag=u"default10001")
        self.run_new_conversation(
            parent.key, parent.delivery_tag_pool, parent.delivery_tag)

    def test_end(self):
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.ended())
        response = self.client.post(reverse('sequential_send:end', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('sequential_send:show', kwargs={
            'conversation_key': conversation.key}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Sequential Send ended")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.ended())

    def test_group_selection(self):
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.is_client_initiated())
        response = self.client.post(reverse('sequential_send:people',
            kwargs={'conversation_key': conversation.key}), {'groups': [
                    grp.key for grp in self.contact_store.list_groups()]})
        self.assertRedirects(
            response, reverse('sequential_send:start', kwargs={
                    'conversation_key': conversation.key}))

    def test_edit_conversation_schedule_config(self):
        conversation = self.get_wrapped_conv()
        self.assertEqual(conversation.metadata, None)
        response = self.client.post(reverse('sequential_send:edit',
            kwargs={'conversation_key': conversation.key}), {
                'schedule-recurring': ['daily'],
                'schedule-days': [''],
                'schedule-time': ['12:00:00'],
                'messages-TOTAL_FORMS': ['1'],
                'messages-INITIAL_FORMS': ['0'],
                'messages-MAX_NUM_FORMS': [''],
                'messages-0-message': [''],
                'messages-0-DELETE': [''],
            })
        self.assertRedirects(
            response, reverse('sequential_send:people', kwargs={
                    'conversation_key': conversation.key}))
        conversation = self.get_wrapped_conv()
        self.assertEqual(conversation.metadata, {
            u'messages': [],
            u'schedule': {
                u'recurring': u'daily',
                u'days': u'',
                u'time': u'12:00:00'}})

    def test_start(self):
        consumer = self.get_cmd_consumer()
        # Acquire the tag here to fake the parent conv already having it.
        self.get_wrapped_conv().acquire_tag()

        response = self.client.post(reverse('sequential_send:start', kwargs={
            'conversation_key': self.conv_key}))
        self.assertRedirects(response, reverse('sequential_send:show', kwargs={
            'conversation_key': self.conv_key}))

        conversation = self.get_wrapped_conv()
        [cmd] = self.fetch_cmds(consumer)
        [batch] = conversation.get_batches()
        [] = list(batch.tags)
        [contact] = self.get_contacts_for_conversation(conversation)
        msg_options = {
            "transport_type": "sms",
            "transport_name": self.transport_name,
            "from_addr": "default10001",
            "helper_metadata": {
                "tag": {"tag": ["longcode", "default10001"]},
                "go": {"user_account": conversation.user_account.key},
                },
            }

        self.assertEqual(cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            conversation_type=conversation.conversation_type,
            conversation_key=conversation.key,
            is_client_initiated=conversation.is_client_initiated(),
            batch_id=batch.key,
            msg_options=msg_options,
            dedupe=False,
            ))

    def test_send_fails(self):
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('sequential_send:start', kwargs={
            'conversation_key': self.conv_key}), follow=True)
        self.assertRedirects(
            response, reverse('sequential_send:start', kwargs={
                    'conversation_key': self.conv_key}))
        [] = self.fetch_cmds(consumer)
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Requested tag not pre-acquired.")

    def test_show(self):
        response = self.client.get(reverse('sequential_send:show', kwargs={
            'conversation_key': self.conv_key}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.subject, 'Test Conversation')
