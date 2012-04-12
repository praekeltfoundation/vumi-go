import operator
import datetime
import redis

from django.db import models
from django.conf import settings

from go.contacts.models import Contact
from go.vumitools import VumiApi

from vxpolls.manager import PollManager


redis = redis.Redis(**settings.VXPOLLS_REDIS_CONFIG)

def get_delivery_classes():
    # TODO: Unhardcode this when we have more configurable delivery classes.
    return [
        ('sms', 'SMS'),
        ('gtalk', 'Google Talk'),
        ]

CONVERSATION_TYPES = (
    ('bulk_message', 'Send Bulk SMS and track replies'),
    ('survey', 'Interactive Survey'),
)

class Conversation(models.Model):
    """A conversation with an audience"""
    user = models.ForeignKey('auth.User')
    subject = models.CharField('Conversation Name', max_length=255)
    message = models.TextField('Message')
    start_date = models.DateField()
    start_time = models.TimeField()
    end_date = models.DateField(null=True)
    end_time = models.TimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    groups = models.ManyToManyField('contacts.ContactGroup')
    previewcontacts = models.ManyToManyField('contacts.Contact')
    conversation_type = models.CharField('Conversation Type', max_length=255,
        choices=CONVERSATION_TYPES, default='bulk_message')
    delivery_class = models.CharField(max_length=255, null=True)

    def people(self):
        return Contact.objects.filter(groups__in=self.groups.all())

    def ended(self):
        return self.end_time is not None

    def end_conversation(self):
        now = datetime.datetime.utcnow()
        self.end_date = now.date()
        self.end_time = now.time()
        self.save()
        self._release_tags()

    def send_preview(self):
        approval_message = "APPROVE? " + self.message
        batch = self._send_batch(self.delivery_class, approval_message,
                                 self.previewcontacts.all())
        batch.preview_batch = self
        batch.save()

    def preview_status(self):
        batches = self.preview_batch_set.all()
        messages = self._get_messages(self.delivery_class, batches)
        replies = self._get_replies(self.delivery_class, batches)
        contacts = dict((c, 'waiting to send') for c in
                        self.previewcontacts.all())
        awaiting_reply = 'awaiting reply'
        for contact, msg in messages:
            if contact in contacts:
                contacts[contact] = awaiting_reply
        for contact, reply in replies:
            if contact in contacts and contacts[contact] == awaiting_reply:
                contents = (reply['content'] or '').strip().lower()
                contacts[contact] = ('approved'
                                     if contents in ('approve', 'yes')
                                     else 'denied')
                if contacts[contact] == 'approved':
                    self._release_preview_tags()
        return sorted(contacts.items())

    def send_messages(self):
        batch = self._send_batch(
            self.delivery_class, self.message, self.people())
        batch.message_batch = self
        batch.save()

    def start_survey(self):
        pm = PollManager(redis, settings.VXPOLLS_PREFIX)
        poll_id = 'poll-%s' % (self.pk,)
        poll = pm.get(poll_id)
        tagpool, transport_type = self.delivery_info(self.delivery_class)
        if poll.questions:
            first_question_copy = poll.questions[0]['copy']
            for contact in self.people():
                addr = contact.addr_for(transport_type)
                if addr:
                    participant = pm.get_participant(addr)
                    next_question = poll.get_next_question(participant, last_index=-1)
                    # save state so we're expecting an answer
                    # next time around.
                    participant.has_unanswered_question = True
                    poll.set_last_question(participant, next_question)
                    pm.save_participant(participant)

            batch = self._send_batch(
                self.delivery_class, first_question_copy, self.people()
            )
            batch.message_batch = self
            batch.save()

    def delivery_class_description(self):
        delivery_classes = dict(get_delivery_classes())
        description = delivery_classes.get(self.delivery_class)
        if description is None:
            description = "Unknown"
        return description

    def replies(self):
        batches = self.message_batch_set.all()
        reply_statuses = []
        for contact, reply in self._get_replies(self.delivery_class, batches):
            delivery_classes = dict(get_delivery_classes())
            reply_statuses.append({
                'type': self.delivery_class,
                'source': delivery_classes[self.delivery_class],
                'contact': contact,
                'time': reply['timestamp'],
                'content': reply['content'],
                })
        return sorted(reply_statuses, key=lambda reply: reply['time'],
                        reverse=True)

    def sent_messages(self):
        batches = self.message_batch_set.all()
        outbound_statuses = []
        sent_messages = self._get_messages(self.delivery_class, batches)
        for contact, message in sent_messages:
            delivery_classes = dict(get_delivery_classes())
            outbound_statuses.append({
                'type': self.delivery_class,
                'source': delivery_classes[self.delivery_class],
                'contact': contact,
                'time': message['timestamp'],
                'content': message['content']
                })
        return sorted(outbound_statuses, key=lambda sent: sent['time'],
                        reverse=True)

    @staticmethod
    def vumi_api():
        return VumiApi(settings.VUMI_API_CONFIG)

    def delivery_info(self, delivery_class):
        """Return a delivery information for a given delivery_class."""
        # TODO: remove hard coded delivery class to tagpool and transport_type
        #       mapping
        if delivery_class == 'sms':
            return "ambient", "sms"
        elif delivery_class == 'gtalk':
            return "gtalk", "xmpp"
        else:
            raise ConversationSendError("Unknown delivery class %r"
                                        % (delivery_class,))

    def tag_message_options(self, tagpool, tag):
        """Return message options for tagpool and tag."""
        # TODO: this is hardcoded for ambient and gtalk pool currently
        if tagpool == "ambient":
            return {
                "from_addr": tag[1],
                "transport_name": "smpp_transport",
                "transport_type": "sms",
                }
        elif tagpool == "gtalk":
            return {
                "from_addr": tag[1],
                "transport_name": "gtalk_vumigo",
                "transport_type": "xmpp",
                }
        else:
            raise ConversationSendError("Unknown tagpool %r" % (tagpool,))

    def _send_batch(self, delivery_class, message, contacts):
        if delivery_class is None:
            raise ConversationSendError("No delivery class specified.")
        if self.ended():
            raise ConversationSendError("Conversation has already ended --"
                                        " no more messages may be sent.")
        vumiapi = self.vumi_api()
        tagpool, transport_type = self.delivery_info(delivery_class)
        addrs = [contact.addr_for(transport_type) for contact in contacts]
        addrs = [addr for addr in addrs if addr]
        print 'addrs', addrs
        tag = vumiapi.acquire_tag(tagpool)
        print 'tag', tag
        if tag is None:
            raise ConversationSendError("No spare messaging tags.")
        msg_options = self.tag_message_options(tagpool, tag)
        batch_id = vumiapi.batch_start([tag])
        batch = MessageBatch(batch_id=batch_id)
        batch.save()
        print 'sending bactch', batch_id, message, msg_options, addrs
        vumiapi.batch_send(batch_id, message, msg_options, addrs)
        return batch

    def _release_preview_tags(self):
        self._release_batches(self.preview_batch_set.all())

    def _release_message_tags(self):
        self._release_batches(self.message_batch_set.all())

    def _release_batches(self, batches):
        vumiapi = self.vumi_api()
        for batch in batches:
            vumiapi.batch_done(batch.batch_id)
            for tag in vumiapi.batch_tags(batch.batch_id):
                vumiapi.release_tag(tag)

    def _release_tags(self):
        self._release_preview_tags()
        self._release_message_tags()

    def _get_helper(self, delivery_class, batches, addr_func, batch_msg_func):
        """Return a list of (Contact, reply_msg) tuples."""
        if delivery_class is None:
            return []
        _tagpool, transport_type = self.delivery_info(delivery_class)

        replies = []
        for batch in batches:
            for reply in batch_msg_func(batch.batch_id):
                try:
                    contact = Contact.for_addr(self.user, transport_type,
                                               addr_func(reply))
                except (Contact.DoesNotExist, Contact.MultipleObjectsReturned):
                    continue
                replies.append((contact, reply))
        return replies

    def _get_replies(self, delivery_class, batches):
        vumiapi = self.vumi_api()
        addr_func = operator.itemgetter('from_addr')
        batch_msg_func = vumiapi.batch_replies
        return self._get_helper(delivery_class, batches,
                                addr_func, batch_msg_func)

    def _get_messages(self, delivery_class, batches):
        vumiapi = self.vumi_api()
        addr_func = operator.itemgetter('to_addr')
        batch_msg_func = vumiapi.batch_messages
        return self._get_helper(delivery_class, batches,
                                addr_func, batch_msg_func)

    class Meta:
        ordering = ['-created_at']
        get_latest_by = 'created_at'

    def __unicode__(self):
        return self.subject


class MessageBatch(models.Model):
    """A set of messages that belong to a conversation.

    The full data about messages is stored in the Vumi API
    message store. This table is just a link from Vumi Go's
    conversations to the Vumi API's batches.
    """
    batch_id = models.CharField(max_length=32)  # uuid4 as hex
    preview_batch = models.ForeignKey(Conversation,
                                      related_name="preview_batch_set",
                                      null=True)
    message_batch = models.ForeignKey(Conversation,
                                      related_name="message_batch_set",
                                      null=True)


class ConversationSendError(Exception):
    """Raised if there are no tags available for a given conversation."""
