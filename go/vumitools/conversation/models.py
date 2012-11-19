# -*- test-case-name: go.vumitools.tests.test_conversation -*-

from uuid import uuid4
from datetime import datetime

from vumi.persist.model import Model, Manager, ModelMigrator
from vumi.persist.fields import (
    Unicode, ManyToMany, ForeignKey, Timestamp, Json)
from vumi.components.message_store import Batch

from twisted.internet.defer import returnValue

from go.vumitools.account import UserAccount, PerAccountStore
from go.vumitools.contact import ContactGroup
# from go.vumitools.conversation.old_models import ConversationVNone


CONVERSATION_TYPES = [
    ('bulk_message', 'Send Bulk SMS and track replies'),
    ('survey', 'Interactive Survey'),
    ('multi_survey', 'Multi-stage Interactive Survey'),
]

CONVERSATION_DRAFT = 'draft'
CONVERSATION_RUNNING = 'running'
CONVERSATION_FINISHED = 'finished'


class ConversationV1Migrator(ModelMigrator):
    def migrate_from_None(self, mdata):
        # Migrator assertions
        assert self.data_version is None
        assert self.model_class.VERSION == 1

        # Data assertions
        assert mdata.data['VERSION'] is None
        assert set(mdata.data.keys()) == set([
            'VERSION',
            'end_timestamp', 'conversation_type', 'start_timestamp',
            'created_at', 'subject', 'metadata', 'message',
            'delivery_class', 'delivery_tag', 'delivery_tag_pool',
            ])
        assert set(mdata.index.keys()) == set([
            'user_account_bin', 'end_timestamp_bin'])

        # Actual migration
        new_data = {}
        for k, v in mdata.data.iteritems():
            if k in set(['VERSION', 'subject', 'message', 'metadata']):
                # These are different in the new version.
                continue
            new_data[k] = v
        new_data.update({
            'VERSION': 1,
            'config': mdata.data['metadata'] or {},
            'name': mdata.data['subject'],
            })
        new_data['config']['content'] = mdata.data['message']
        mdata.data = new_data
        return mdata


class Conversation(Model):
    """A conversation with an audience"""

    # TODO:
    #
    #  * Indexed status field: "started", "draft", "ended", etc.
    #  * Index created_at, start_timestamp
    #  * Index conversation_type

    VERSION = 1
    MIGRATOR = ConversationV1Migrator

    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255)
    config = Json(default=dict)
    start_timestamp = Timestamp()
    end_timestamp = Timestamp(null=True, index=True)
    created_at = Timestamp(default=datetime.utcnow)

    groups = ManyToMany(ContactGroup)
    conversation_type = Unicode()
    delivery_class = Unicode(null=True)
    delivery_tag_pool = Unicode(null=True)
    delivery_tag = Unicode(null=True)

    batches = ManyToMany(Batch)

    def started(self):
        # TODO: Better way to tell if we've started than looking for batches.
        return bool(self.batches.keys())

    def ended(self):
        return self.end_timestamp is not None

    def running(self):
        return self.started() and not self.ended()

    def get_status(self):
        """
        Get the status of this conversation

        :rtype: str, (CONVERSATION_FINISHED, CONVERSATION_RUNNING, or
            CONVERSATION_DRAFT)

        """
        if self.ended():
            return CONVERSATION_FINISHED
        elif self.running():
            return CONVERSATION_RUNNING
        else:
            return CONVERSATION_DRAFT

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
    def new_conversation(self, conversation_type, name, config, **fields):
        conversation_id = uuid4().get_hex()
        start_timestamp = fields.pop('start_timestamp', datetime.utcnow())

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
