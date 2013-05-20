# -*- test-case-name: go.vumitools.tests.test_conversation -*-

from uuid import uuid4
from datetime import datetime

from vumi.persist.model import Model, Manager
from vumi.persist.fields import (
    Unicode, ManyToMany, ForeignKey, Timestamp, Json, ListOf)
from vumi.components.message_store import Batch

from twisted.internet.defer import returnValue

from go.vumitools.account import UserAccount, PerAccountStore
from go.vumitools.contact import ContactGroup
from go.vumitools.conversation.migrators import ConversationMigrator


CONVERSATION_ACTIVE = u'active'
CONVERSATION_ARCHIVED = u'archived'

CONVERSATION_STARTING = u'starting'
CONVERSATION_RUNNING = u'running'
CONVERSATION_STOPPING = u'stopping'
CONVERSATION_STOPPED = u'stopped'


class Conversation(Model):
    """A conversation with an audience"""

    VERSION = 2
    MIGRATOR = ConversationMigrator

    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255)
    description = Unicode(default=u'')
    conversation_type = Unicode(index=True)
    config = Json(default=dict)
    extra_endpoints = ListOf(Unicode())

    created_at = Timestamp(default=datetime.utcnow, index=True)
    archived_at = Timestamp(null=True, index=True)

    archive_status = Unicode(default=CONVERSATION_ACTIVE, index=True)
    status = Unicode(default=CONVERSATION_STOPPED, index=True)

    groups = ManyToMany(ContactGroup)
    batches = ManyToMany(Batch)

    delivery_class = Unicode(null=True)
    delivery_tag_pool = Unicode(null=True)
    delivery_tag = Unicode(null=True)

    def active(self):
        return self.archive_status == CONVERSATION_ACTIVE

    def archived(self):
        return self.archive_status == CONVERSATION_ARCHIVED

    def ended(self):
        # TODO: Get rid of this once the old UI finally goes away.
        return self.archived()

    def running(self):
        return self.status == CONVERSATION_RUNNING

    def is_draft(self):
        # TODO: Get rid of this once the old UI finally goes away.
        return self.active() and self.status == CONVERSATION_STOPPED

    def get_status(self):
        """Get the status of this conversation.

        Possible values are:

          * CONVERSATION_STARTING
          * CONVERSATION_RUNNING
          * CONVERSATION_STOPPING
          * CONVERSATION_STOPPED

        :rtype: str

        """
        return self.status

    # The following are to keep the implementation of this stuff in the model
    # rather than potentially multiple external places.
    def set_status_starting(self):
        self.status = CONVERSATION_STARTING

    def set_status_started(self):
        self.status = CONVERSATION_RUNNING

    def set_status_stopping(self):
        self.status = CONVERSATION_STOPPING

    def set_status_stopped(self):
        self.status = CONVERSATION_STOPPED

    def set_status_finished(self):
        self.archive_status = CONVERSATION_ARCHIVED

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

    def get_routing_name(self):
        return ':'.join((self.conversation_type, self.key))


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
    def new_conversation(self, conversation_type, name, description, config,
                         **fields):
        conversation_id = uuid4().get_hex()

        # These are foreign keys.
        groups = fields.pop('groups', [])

        conversation = self.conversations(
            conversation_id, user_account=self.user_account_key,
            conversation_type=conversation_type, name=name,
            description=description, config=config, **fields)

        for group in groups:
            conversation.add_group(group)

        conversation = yield conversation.save()
        returnValue(conversation)

    @Manager.calls_manager
    def list_running_conversations(self):
        keys = yield self.conversations.index_lookup(
            'status', CONVERSATION_RUNNING).get_keys()
        returnValue(keys)

    @Manager.calls_manager
    def list_active_conversations(self):
        # We need to list things by both the old-style 'status' index and the
        # new-style 'archive_status' index, at least until we've migrated all
        # old-style conversations to v2.
        keys = yield self.conversations.index_lookup(
            'archive_status', CONVERSATION_ACTIVE).get_keys()
        keys.extend((yield self.conversations.index_lookup(
            'status', 'draft').get_keys()))  # No more constant for this.
        keys.extend((yield self.conversations.index_lookup(
            'status', CONVERSATION_RUNNING).get_keys()))
        returnValue(list(set(keys)))  # Dedupe.

    def load_all_bunches(self, keys):
        # Convenience to avoid the extra attribute lookup everywhere.
        return self.conversations.load_all_bunches(keys)
