from datetime import datetime, timedelta
import uuid

from go.base.tests.utils import VumiGoDjangoTestCase, declare_longcode_tags
from go.vumitools.tests.utils import CeleryTestMixIn
from go.base.utils import vumi_api_for_user

from vumi.message import TransportUserMessage, TransportEvent


class DjangoGoApplicationTestCase(VumiGoDjangoTestCase, CeleryTestMixIn):
    use_riak = True

    TEST_GROUP_NAME = u"Test Group"
    TEST_CONTACT_NAME = u"Name"
    TEST_CONTACT_SURNAME = u"Surname"
    TEST_CONVERSATION_NAME = u"Test Conversation"
    TEST_CONVERSATION_TYPE = u'bulk_message'
    TEST_CONVERSATION_PARAMS = None
    TEST_START_PARAMS = None
    VIEWS_CLASS = None

    # These are used for the mkmsg_in and mkmsg_out helper methods
    transport_name = 'sphex'
    transport_type = 'sms'

    def setUp(self):
        super(DjangoGoApplicationTestCase, self).setUp()
        self.setup_api()
        self.declare_longcode_tags()
        self.setup_celery_for_tests()

    def setup_riak_fixtures(self):
        self.user = self.mk_django_user()
        self.setup_user_api(self.user)

        if self.VIEWS_CLASS is not None:
            self.TEST_CONVERSATION_TYPE = self.VIEWS_CLASS.conversation_type
            self.TEST_START_PARAMS = self.VIEWS_CLASS.conversation_start_params

        # We need a group
        self.group = self.contact_store.new_group(self.TEST_GROUP_NAME)
        self.group_key = self.group.key

        # Also a contact
        self.contact = self.contact_store.new_contact(
            name=self.TEST_CONTACT_NAME, surname=self.TEST_CONTACT_SURNAME,
            msisdn=u"+27761234567")
        self.contact.add_to_group(self.group)
        self.contact.save()
        self.contact_key = self.contact.key

        # And a conversation
        params = {
            'conversation_type': self.TEST_CONVERSATION_TYPE,
            'name': self.TEST_CONVERSATION_NAME,
            'description': u"Test message",
            'delivery_class': u"sms",
            'delivery_tag_pool': u"longcode",
            'groups': [self.group_key],
            'config': {},
            }
        if self.TEST_CONVERSATION_PARAMS:
            params.update(self.TEST_CONVERSATION_PARAMS)
        self.conversation = self.conv_store.new_conversation(**params)
        self.conv_key = self.conversation.key

    def mkconversation(self, **kwargs):
        defaults = {
            'conversation_type': u'bulk_message',
            'name': u'subject',
            'description': u'hello world',
            'config': {},
        }
        defaults.update(kwargs)
        return self.conv_store.new_conversation(**defaults)

    def get_latest_conversation(self):
        # We won't have too many here, so doing it naively is fine.
        conversations = []
        for key in self.conv_store.list_conversations():
            conversations.append(self.conv_store.get_conversation_by_key(key))
        return max(conversations, key=lambda c: c.created_at)

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

    def mkcontact(self, name=None, surname=None, msisdn=u'+1234567890',
                  **kwargs):
        return self.contact_store.new_contact(
            name=unicode(name or self.TEST_CONTACT_NAME),
            surname=unicode(surname or self.TEST_CONTACT_SURNAME),
            msisdn=unicode(msisdn), **kwargs)

    def setup_user_api(self, django_user):
        self.user_api = vumi_api_for_user(django_user)
        # XXX: We assume the tagpool already exists here. We need to rewrite
        #      a lot of this test infrastructure.
        self.add_tagpool_permission(u"longcode")
        self.contact_store = self.user_api.contact_store
        self.contact_store.contacts.enable_search()
        self.contact_store.groups.enable_search()
        self.conv_store = self.user_api.conversation_store

    def declare_longcode_tags(self):
        declare_longcode_tags(self.api)

    def add_tagpool_permission(self, tagpool, max_keys=None):
        permission = self.user_api.api.account_store.tag_permissions(
            uuid.uuid4().hex, tagpool=tagpool, max_keys=max_keys)
        permission.save()
        account = self.user_api.get_user_account()
        account.tagpools.add(permission)
        account.save()

    def acquire_all_longcode_tags(self):
        for _i in range(4):
            self.user_api.acquire_tag(u"longcode")

    def get_api_commands_sent(self):
        consumer = self.get_cmd_consumer()
        return self.fetch_cmds(consumer)

    def put_sample_messages_in_conversation(self, user_api, conversation_key,
                                                message_count,
                                                content_generator=None,
                                                start_timestamp=None,
                                                time_multiplier=10):
        now = start_timestamp or datetime.now().date()
        conversation = user_api.get_wrapped_conversation(conversation_key)
        conversation.start()
        batch_key = conversation.get_latest_batch_key()

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
        permission = self.user_api.api.account_store.application_permissions(
            uuid.uuid4().hex, application=application)
        permission.save()

        account = self.user_api.get_user_account()
        account.applications.add(permission)
        account.save()
