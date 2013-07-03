from datetime import datetime, timedelta
import uuid

from django.core.urlresolvers import reverse

from vumi.message import TransportUserMessage, TransportEvent

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

    # These are used for the mkmsg_in and mkmsg_out helper methods
    transport_name = 'sphex'
    transport_type = 'sms'

    # Set a bunch of attrs to None so we can see if we've set them later.
    group = None
    contact = None
    conversation = None

    def setUp(self):
        super(DjangoGoApplicationTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def setup_user_api(self, django_user=None):
        if django_user is None:
            django_user = self.mk_django_user()
        self.django_user = django_user
        self.user_api = base_utils.vumi_api_for_user(django_user)
        self.contact_store = self.user_api.contact_store
        self.contact_store.contacts.enable_search()
        self.contact_store.groups.enable_search()
        self.conv_store = self.user_api.conversation_store

    def create_conversation(self, **kwargs):
        defaults = {
            'conversation_type': u'test_conversation_type',
            'name': u'conversation name',
            'description': u'hello world',
            'config': {},
        }
        defaults.update(kwargs)
        return self.conv_store.new_conversation(**defaults)

    def _create_group(self, with_contact=False):
        if self.group is not None:
            return
        self.group = self.contact_store.new_group(self.TEST_GROUP_NAME)
        self.group_key = self.group.key
        if with_contact:
            self._create_contact()

    def _create_contact(self):
        if self.contact is not None:
            return
        self.contact = self.contact_store.new_contact(
            name=self.TEST_CONTACT_NAME, surname=self.TEST_CONTACT_SURNAME,
            msisdn=u"+27761234567")
        self.contact.add_to_group(self.group)
        self.contact.save()
        self.contact_key = self.contact.key

    def _create_conversation(self, with_group=True):
        if self.conversation is not None:
            return
        params = {
            'conversation_type': self.TEST_CONVERSATION_TYPE,
            'name': self.TEST_CONVERSATION_NAME,
            'description': u"Test message",
            'config': {},
        }
        if with_group:
            params['groups'] = [self.group]
        if self.TEST_CONVERSATION_PARAMS:
            params.update(self.TEST_CONVERSATION_PARAMS)
        self.conversation = self.create_conversation(**params)
        self.conv_key = self.conversation.key

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

    def mkmsg_ack(self, user_message_id='1', sent_message_id='abc',
                  transport_metadata=None, transport_name=None):
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        return TransportEvent(
            event_type='ack',
            user_message_id=user_message_id,
            sent_message_id=sent_message_id,
            transport_name=transport_name,
            transport_metadata=transport_metadata,
            )

    def mkmsg_nack(self, user_message_id='1', transport_metadata=None,
                    transport_name=None, nack_reason='unknown'):
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        return TransportEvent(
            event_type='nack',
            nack_reason=nack_reason,
            user_message_id=user_message_id,
            transport_name=transport_name,
            transport_metadata=transport_metadata,
            )

    def mkmsg_delivery(self, status='delivered', user_message_id='abc',
                       transport_metadata=None, transport_name=None):
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        return TransportEvent(
            event_type='delivery_report',
            transport_name=transport_name,
            user_message_id=user_message_id,
            delivery_status=status,
            to_addr='+41791234567',
            transport_metadata=transport_metadata,
            )

    def mkmsg_in(self, content='hello world', message_id='abc',
                 to_addr='9292', from_addr='+41791234567', group=None,
                 session_event=None, transport_type=None,
                 helper_metadata=None, transport_metadata=None,
                 transport_name=None):
        if transport_type is None:
            transport_type = self.transport_type
        if helper_metadata is None:
            helper_metadata = {}
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        return TransportUserMessage(
            from_addr=from_addr,
            to_addr=to_addr,
            group=group,
            message_id=message_id,
            transport_name=transport_name,
            transport_type=transport_type,
            transport_metadata=transport_metadata,
            helper_metadata=helper_metadata,
            content=content,
            session_event=session_event,
            timestamp=datetime.now(),
            )

    def mkmsg_out(self, content='hello world', message_id='1',
                  to_addr='+41791234567', from_addr='9292', group=None,
                  session_event=None, in_reply_to=None,
                  transport_type=None, transport_metadata=None,
                  transport_name=None, helper_metadata=None,
                  ):
        if transport_type is None:
            transport_type = self.transport_type
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        if helper_metadata is None:
            helper_metadata = {}
        params = dict(
            to_addr=to_addr,
            from_addr=from_addr,
            group=group,
            message_id=message_id,
            transport_name=transport_name,
            transport_type=transport_type,
            transport_metadata=transport_metadata,
            content=content,
            session_event=session_event,
            in_reply_to=in_reply_to,
            helper_metadata=helper_metadata,
            )
        return TransportUserMessage(**params)

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()

    def put_sample_messages_in_conversation(self, message_count,
                                            content_generator=None,
                                            start_date=None,
                                            time_multiplier=10):
        now = start_date or datetime.now().date()
        batch_key = self.get_wrapped_conv().get_latest_batch_key()

        messages = []
        for i in range(message_count):
            content = (content_generator.next()
                        if content_generator else 'hello')
            msg_in = self.mkmsg_in(from_addr='from-%s' % (i,),
                message_id=TransportUserMessage.generate_id(),
                content=content)
            ts = now - timedelta(hours=i * time_multiplier)
            msg_in['timestamp'] = ts
            msg_out = msg_in.reply('thank you')
            msg_out['timestamp'] = ts
            ack = self.mkmsg_ack(user_message_id=msg_out['message_id'])
            dr = self.mkmsg_delivery(user_message_id=msg_out['message_id'])
            self.api.mdb.add_inbound_message(msg_in, batch_id=batch_key)
            self.api.mdb.add_outbound_message(msg_out, batch_id=batch_key)
            self.api.mdb.add_event(ack)
            self.api.mdb.add_event(dr)
            messages.append((msg_in, msg_out, ack, dr))
        return messages

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

    def setup_conversation(self, started=False, with_group=False,
                           with_contact=False):
        if with_group:
            self._create_group(with_contact=with_contact)
        self._create_conversation(with_group=with_group)
        conv = self.user_api.wrap_conversation(self.conversation)

        if started:
            conv.set_status_started()
            batch_id = conv.start_batch()
            conv.batches.add_key(batch_id)
            conv.save()

    def add_tagpool_permission(self, tagpool, max_keys=None):
        permission = self.api.account_store.tag_permissions(
            uuid.uuid4().hex, tagpool=tagpool, max_keys=max_keys)
        permission.save()
        account = self.user_api.get_user_account()
        account.tagpools.add(permission)
        account.save()
