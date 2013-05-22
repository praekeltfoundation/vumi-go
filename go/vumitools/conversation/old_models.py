from datetime import datetime

from vumi.persist.model import Model
from vumi.persist.fields import (
    Unicode, ManyToMany, ForeignKey, Timestamp, Json)
from vumi.components.message_store import Batch

from go.vumitools.account import UserAccount
from go.vumitools.contact import ContactGroup


CONVERSATION_DRAFT = 'draft'
CONVERSATION_RUNNING = 'running'
CONVERSATION_FINISHED = 'finished'


class ConversationVNone(Model):
    """A conversation with an audience"""

    bucket = 'conversation'

    user_account = ForeignKey(UserAccount)
    subject = Unicode(max_length=255)
    message = Unicode()
    start_timestamp = Timestamp()
    end_timestamp = Timestamp(null=True, index=True)
    created_at = Timestamp(default=datetime.utcnow)

    groups = ManyToMany(ContactGroup)
    conversation_type = Unicode()
    delivery_class = Unicode(null=True)
    delivery_tag_pool = Unicode(null=True)
    delivery_tag = Unicode(null=True)

    batches = ManyToMany(Batch)
    metadata = Json(null=True)

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
        return self.subject

    def get_contacts_addresses(self, contacts):
        """
        Get the contacts assigned to this group with an address attribute
        that is appropriate for this conversation's delivery_class
        """
        addrs = [contact.addr_for(self.delivery_class) for contact in contacts]
        return [addr for addr in addrs if addr]


class ConversationV1(Model):
    """A conversation with an audience"""

    VERSION = 1

    bucket = 'conversation'

    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255)
    description = Unicode(default=u'')
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

    def get_routing_name(self):
        return ':'.join((self.conversation_type, self.key))
