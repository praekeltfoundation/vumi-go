# -*- test-case-name: go.vumitools.tests.test_conversation -*-

from uuid import uuid4
from datetime import datetime

from vumi.persist.model import Model, Manager
from vumi.persist.fields import (
    Unicode, ManyToMany, ForeignKey, Timestamp, Json)
from vumi.components.message_store import Batch

from twisted.internet.defer import returnValue

from go.vumitools.account import UserAccount, PerAccountStore
from go.vumitools.contact import ContactGroup
from go.vumitools.conversation.migrators import ConversationMigrator


CONVERSATION_TYPES = [
    ('bulk_message', 'Send Bulk SMS and track replies'),
    ('survey', 'Interactive Survey'),
    ('multi_survey', 'Multi-stage Interactive Survey'),
]

CONVERSATION_DRAFT = u'draft'
CONVERSATION_RUNNING = u'running'
CONVERSATION_FINISHED = u'finished'


class Conversation(Model):
    """A conversation with an audience"""

    VERSION = 1
    MIGRATOR = ConversationMigrator

    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255)
    conversation_type = Unicode(index=True)
    config = Json(default=dict)

    created_at = Timestamp(default=datetime.utcnow, index=True)
    start_timestamp = Timestamp(index=True)
    end_timestamp = Timestamp(null=True, index=True)
    status = Unicode(default=CONVERSATION_DRAFT, index=True)

    groups = ManyToMany(ContactGroup)
    batches = ManyToMany(Batch)

    delivery_class = Unicode(null=True)
    delivery_tag_pool = Unicode(null=True)
    delivery_tag = Unicode(null=True)

    def started(self):
        return self.running() or self.ended()

    def ended(self):
        return self.status == CONVERSATION_FINISHED

    def running(self):
        return self.status == CONVERSATION_RUNNING

    def get_status(self):
        """
        Get the status of this conversation

        :rtype: str, (CONVERSATION_FINISHED, CONVERSATION_RUNNING, or
            CONVERSATION_DRAFT)

        """
        return self.status

    # The following are to keep the implementation of this stuff in the model
    # rather than potentially multiple external places.
    def set_status_started(self):
        self.status = CONVERSATION_RUNNING

    def set_status_finished(self):
        self.status = CONVERSATION_FINISHED

    def add_group(self, group):
        if isinstance(group, ContactGroup):
            self.groups.add(group)
        else:
            self.groups.add_key(group)

    def __unicode__(self):
        return self.name

    def get_contacts_addresses(self, contacts):
        """
        Get the contacts assigned to this group with an address attribute
        that is appropriate for this conversation's delivery_class
        """
        addrs = [contact.addr_for(self.delivery_class) for contact in contacts]
        return [addr for addr in addrs if addr]


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

    @Manager.calls_manager
    def new_conversation(self, conversation_type, name, config,
                         start_timestamp=None, **fields):
        conversation_id = uuid4().get_hex()
        start_timestamp = start_timestamp or datetime.utcnow()

        # These are foreign keys.
        groups = fields.pop('groups', [])

        conversation = self.conversations(
            conversation_id, user_account=self.user_account_key,
            conversation_type=conversation_type,
            name=name, config=config, start_timestamp=start_timestamp,
            **fields)

        for group in groups:
            conversation.add_group(group)

        conversation = yield conversation.save()
        returnValue(conversation)

    @Manager.calls_manager
    def list_running_conversations(self):
        # We need to list things by both the old-style 'end_timestamp' index
        # and the new-style 'status' index, at least until we've migrated all
        # old-style conversations to v1.
        keys = yield self.conversations.index_lookup(
            'status', CONVERSATION_RUNNING).get_keys()
        keys.extend((yield self._list_oldstyle_running_conversations()))
        returnValue(list(set(keys)))  # Dedupe

    @Manager.calls_manager
    def _list_oldstyle_running_conversations(self):
        keys = yield self.conversations.index_lookup(
            'end_timestamp', None).get_keys()
        # NOTE: This assumes that we don't have very large numbers of active
        #       conversations.
        filtered_keys = []
        for convs_bunch in self.load_all_bunches(keys):
            for conv in (yield convs_bunch):
                if conv.running:
                    filtered_keys = conv.key
        returnValue(filtered_keys)

    @Manager.calls_manager
    def list_active_conversations(self):
        # We need to list things by both the old-style 'end_timestamp' index
        # and the new-style 'status' index, at least until we've migrated all
        # old-style conversations to v1.
        keys = yield self.conversations.index_lookup(
            'status', CONVERSATION_RUNNING).get_keys()
        keys.extend((yield self.conversations.index_lookup(
            'status', CONVERSATION_DRAFT).get_keys()))
        keys.extend((yield self.conversations.index_lookup(
            'end_timestamp', None).get_keys()))
        returnValue(list(set(keys)))  # Dedupe.

    def load_all_bunches(self, keys):
        # Convenience to avoid the extra attribute lookup everywhere.
        return self.conversations.load_all_bunches(keys)
