# -*- test-case-name: go.vumitools.tests.test_conversation -*-

import operator
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import Unicode, Timestamp, ManyToMany, ForeignKey
from vumi.persist.message_store import MessageStore, Batch

from go.vumitools import VumiApi
from go.vumitools.account import UserAccount, PerAccountStore
from go.vumitools.contact import Contact, ContactGroup


def get_delivery_classes():
    # TODO: Unhardcode this when we have more configurable delivery classes.
    return [
        ('shortcode', 'SMS Short code'),
        ('longcode', 'SMS Long code'),
        ('xmpp', 'Google Talk'),
        ]


CONVERSATION_TYPES = (
    ('bulk_message', 'Send Bulk SMS and track replies'),
    ('survey', 'Interactive Survey'),
)


class Conversation(Model):
    """A conversation with an audience"""
    user_account = ForeignKey(UserAccount)
    subject = Unicode(max_length=255)
    message = Unicode()
    start_time = Timestamp()
    end_time = Timestamp(null=True)
    created_at = Timestamp(default=datetime.utcnow)
    groups = ManyToMany(ContactGroup)
    preview_contacts = ManyToMany(Contact)
    conversation_type = Unicode()
    # Was:
    # conversation_type = models.CharField('Conversation Type', max_length=255,
    #     choices=CONVERSATION_TYPES, default='bulk_message')
    delivery_class = Unicode(max_length=255, null=True)
    preview_batches = ManyToMany(Batch)

    def ended(self):
        return self.end_time is not None


class ConversationStore(PerAccountStore):
    def setup_proxies(self):
        self.conversations = self.manager.proxy(Conversation)
        # self.message_store = MessageStore(self.base_manager)

    @Manager.calls_manager
    def end_conversation(self, conversation):
        conversation.end_time = datetime.utcnow()
        yield conversation.save()
        yield self._release_tags()

    @Manager.calls_manager
    def people(self, conversation):
        # TODO: Dedup this?
        contacts = []
        for group in (yield conversation.groups.get_all()):
            contacts.extend((yield group.backlinks.contacts()))
        returnValue(contacts)

    @Manager.calls_manager
    def preview_status(self, conversation):
        # TODO: Make this less hacky.
        # NOTE: This does not release the preview tags.
        contacts = yield conversation.preview_contacts.get_all()
        batches = yield conversation.preview_batches.get_all(
            self.base_manager)
        messages = []
        replies = []
        for batch in batches:
            messages.extend((yield batch.backlinks.outboundmessages()))
            replies.extend((yield batch.backlinks.inboundmessages()))

        statuses = {}

        for message in messages:
            statuses[message.msg['to_addr']] = 'awaiting reply'

        for message in replies:
            if message.msg['from_addr'] not in statuses:
                # Don't accept approvals for previews we haven't sent.
                continue
            content = (message.msg['content'] or '').strip().lower()
            status = 'denied'
            if content in ('approve', 'yes'):
                status = 'approved'
            statuses[message.msg['from_addr']] = status

        get_status = lambda c: statuses.get(c.addr_for(self.delivery_class),
                                            'waiting to send')
        returnValue([(contact, get_status(contact)) for contact in contacts])


class ConversationSendError(Exception):
    """Raised if there are no tags available for a given conversation."""
