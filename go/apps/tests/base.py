import uuid

from django.core.urlresolvers import reverse

from go.base.utils import get_conversation_view_definition
from go.base.tests.utils import VumiGoDjangoTestCase
from go.base import utils as base_utils


class DjangoGoApplicationTestCase(VumiGoDjangoTestCase):
    use_riak = True

    TEST_GROUP_NAME = u"Test Group"
    TEST_CONTACT_NAME = u"Name"
    TEST_CONTACT_SURNAME = u"Surname"
    TEST_CONVERSATION_NAME = u"Test Conversation"
    TEST_CONVERSATION_TYPE = u'bulk_message'
    TEST_CONVERSATION_PARAMS = None
    TEST_CHANNEL_METADATA = None

    def setUp(self):
        super(DjangoGoApplicationTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def setup_conversation(self, started=False, with_group=False,
                           with_contact=False, with_channel=False):
        params = {
            'conversation_type': self.TEST_CONVERSATION_TYPE,
            'name': self.TEST_CONVERSATION_NAME,
            'description': u"Test message",
            'config': {},
        }
        if with_group:
            self.group = self.contact_store.new_group(self.TEST_GROUP_NAME)
            params['groups'] = [self.group]
            if with_contact:
                self.contact = self.contact_store.new_contact(
                    msisdn=u"+27761234567", name=self.TEST_CONTACT_NAME,
                    surname=self.TEST_CONTACT_SURNAME, groups=[self.group])
        if self.TEST_CONVERSATION_PARAMS:
            params.update(self.TEST_CONVERSATION_PARAMS)
        self.conversation = self.create_conversation(started=started, **params)
        self.conv_key = self.conversation.key
        if with_channel:
            self.declare_tags("pool", 1, self.TEST_CHANNEL_METADATA or {})
            tag = (u'pool', u'default1')
            self._acquire_channel_for_conversation(self.conversation, tag)

    def _acquire_channel_for_conversation(self, conv, tag):
        self.user_api.acquire_specific_tag(tag)
        channel = self.user_api.get_channel(tag)
        user_account = self.user_api.get_user_account()
        rt = user_account.routing_table
        rt.add_entry(
            conv.get_connector(), 'default',
            channel.get_connector(), 'default')
        rt.add_entry(
            channel.get_connector(), 'default',
            conv.get_connector(), 'default')
        user_account.save()

    def get_latest_conversation(self):
        # We won't have too many here, so doing it naively is fine.
        conversations = []
        for key in self.conv_store.list_conversations():
            conversations.append(self.conv_store.get_conversation_by_key(key))
        return max(conversations, key=lambda c: c.created_at)

    def post_new_conversation(self, name='conversation name'):
        return self.client.post(self.get_new_view_url(), {
            'name': name,
            'conversation_type': self.TEST_CONVERSATION_TYPE,
        })

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()

    def get_contacts_for_conversation(self, conversation):
        return self.contact_store.get_contacts_for_conversation(conversation)

    def add_app_permission(self, application):
        permission = self.api.account_store.application_permissions(
            uuid.uuid4().hex, application=application)
        permission.save()

        account = self.user_api.get_user_account()
        account.applications.add(permission)
        account.save()

    def get_view_url(self, view, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        view_def = get_conversation_view_definition(
            self.TEST_CONVERSATION_TYPE)
        return view_def.get_view_url(view, conversation_key=conv_key)

    def get_new_view_url(self):
        return reverse('conversations:new_conversation')

    def get_action_view_url(self, action_name, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        return reverse('conversations:conversation_action', kwargs={
            'conversation_key': conv_key, 'action_name': action_name})

    def get_wrapped_conv(self, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        return self.user_api.get_wrapped_conversation(conv_key)

    def add_messages_to_conv(self, message_count, conversation=None, **kwargs):
        if conversation is None:
            conversation = self.get_wrapped_conv()
        return super(DjangoGoApplicationTestCase, self).add_messages_to_conv(
            message_count, conversation, **kwargs)
