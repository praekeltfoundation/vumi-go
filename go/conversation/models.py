import operator
from django.db import models
from django.conf import settings
from go.contacts.models import Contact
from go.vumitools import VumiApi


def get_delivery_classes():
    # TODO: Unhardcode this when we have more configurable delivery classes.
    return [
        ('sms', 'SMS'),
        ('gtalk', 'Google Talk'),
        ]


class Conversation(models.Model):
    """A conversation with an audience"""
    user = models.ForeignKey('auth.User')
    subject = models.CharField('Conversation Name', max_length=255)
    message = models.TextField('Message')
    start_date = models.DateField()
    start_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    groups = models.ManyToManyField('contacts.ContactGroup')
    previewcontacts = models.ManyToManyField('contacts.Contact')
    delivery_class = models.CharField(max_length=255, null=True)

    def people(self):
        return Contact.objects.filter(groups__in=self.groups.all())

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
        return sorted(contacts.items())

    def send_messages(self):
        batch = self._send_batch(
            self.delivery_class, self.message, self.people())
        batch.message_batch = self
        batch.save()

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
        return reply_statuses

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
                "from_addr": tag,
                "transport_name": "ambient",
                "transport_type": "sms",
                }
        elif tagpool == "gtalk":
            return {
                "from_addr": tag,
                "transport_name": "gtalk_vumigo",
                "transport_type": "xmpp",
                }
        else:
            raise ConversationSendError("Unknown tagpool %r" % (tagpool,))

    def _send_batch(self, delivery_class, message, contacts):
        if delivery_class is None:
            raise ConversationSendError("No delivery class specified.")
        vumiapi = self.vumi_api()
        tagpool, transport_type = self.delivery_info(delivery_class)
        addrs = [contact.addr_for(transport_type) for contact in contacts]
        addrs = [addr for addr in addrs if addr]
        tag = vumiapi.acquire_tag(tagpool)
        if tag is None:
            raise ConversationSendError("No spare messaging tags.")
        msg_options = self.tag_message_options(tagpool, tag)
        batch_id = vumiapi.batch_start([tag])
        batch = MessageBatch(batch_id=batch_id)
        batch.save()
        vumiapi.batch_send(batch_id, message, msg_options, addrs)
        return batch

    def _get_helper(self, delivery_class, batches, addr_func, batch_msg_func):
        """Return a list of (Contact, reply_msg) tuples."""
        if delivery_class is None:
            return []
        _tagpool, transport_type = self.delivery_info(delivery_class)

        replies = []
        for batch in batches:
            for reply in batch_msg_func(batch.batch_id):
                try:
                    contact = Contact.for_addr(transport_type,
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
        ordering = ['-updated_at']
        get_latest_by = 'updated_at'

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
