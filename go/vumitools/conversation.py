# -*- test-case-name: go.vumitools.tests.test_conversation -*-

from uuid import uuid4
from datetime import datetime

from vumi.persist.model import Model, Manager
from vumi.persist.message_store import Batch
from vumi.persist.fields import Unicode, ManyToMany, ForeignKey, Timestamp

from twisted.internet.defer import returnValue

from go.vumitools.account import UserAccount, PerAccountStore
from go.vumitools.contact import ContactGroup


def get_combined_delivery_classes():
    return (get_client_init_delivery_classes() +
                get_server_init_delivery_classes())


def get_server_init_delivery_classes():
    return [
        ('sms', [
            ('shortcode', 'Short code'),
            ('longcode', 'Long code'),
        ]),
        ('gtalk', [
            ('xmpp', 'Google Talk'),
        ])
    ]


def get_client_init_delivery_classes():
    return [
        ('ussd', [
            ('truteq', '*120*646*4*1*...#'),
            ('integrat', '*120*99*987*10*...#'),
        ]),
    ]


CONVERSATION_TYPES = [
    ('bulk_message', 'Send Bulk SMS and track replies'),
    ('survey', 'Interactive Survey'),
]


CONVERSATION_DRAFT = 'draft'
CONVERSATION_RUNNING = 'running'
CONVERSATION_FINISHED = 'finished'


class Conversation(Model):
    """A conversation with an audience"""
    user_account = ForeignKey(UserAccount)
    subject = Unicode(max_length=255)
    message = Unicode()
    start_timestamp = Timestamp()
    end_timestamp = Timestamp(null=True)
    created_at = Timestamp(default=datetime.utcnow)

    groups = ManyToMany(ContactGroup)
    conversation_type = Unicode()
    delivery_class = Unicode(null=True)
    delivery_tag_pool = Unicode(null=True)

    batches = ManyToMany(Batch)

    def ended(self):
        return self.end_timestamp is not None

    def is_client_initiated(self):
        """
        Check whether this conversation can only be initiated by a client.

        :rtype: bool
        """
        return (self.delivery_class not in
                get_server_init_delivery_class_names())

    def get_status(self):
        """
        Get the status of this conversation

        :rtype: str, (CONVERSATION_FINISHED, CONVERSATION_RUNNING, or
            CONVERSATION_DRAFT)

        """
        if self.ended():
            return CONVERSATION_FINISHED
        elif self.batches.keys():
            return CONVERSATION_RUNNING
        else:
            return CONVERSATION_DRAFT

    def delivery_class_description(self):
        """
        FIXME: this is a hack
        """
        delivery_classes = dict(get_combined_delivery_classes())
        tag_pools = dict(delivery_classes.get(self.delivery_class))
        description = tag_pools.get(self.delivery_tag_pool)
        if description is None:
            description = "Unknown"
        return description

    def add_group(self, group):
        if isinstance(group, ContactGroup):
            self.groups.add(group)
        else:
            self.groups.add_key(group)

    def __unicode__(self):
        return self.subject


class ConversationStore(PerAccountStore):
    def setup_proxies(self):
        self.conversations = self.manager.proxy(Conversation)

    @Manager.calls_manager
    def list_conversations(self):
        # Not stale, because we're using backlinks.
        account = yield self.get_user_account()
        conversations = yield account.backlinks.conversations(self.manager)
        returnValue(conversations)

    def get_conversation_by_key(self, key):
        return self.conversations.load(key)

    def new_conversation(self, conversation_type, subject, message,
        start_timestamp=None, **fields):
        conversation_id = uuid4().get_hex()
        start_timestamp = start_timestamp or datetime.utcnow()

        # These are foreign keys.
        groups = fields.pop('groups', [])

        conversation = self.conversations(
            conversation_id, user_account=self.user_account_key,
            conversation_type=conversation_type,
            subject=subject, message=message,
            start_timestamp=start_timestamp,
            **fields)

        for group in groups:
            conversation.add_group(group)

        return conversation.save()
