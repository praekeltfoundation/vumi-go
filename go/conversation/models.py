from django.db import models
from go.contacts.models import Contact
from go.vumitools import VumiApi


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

    def people(self):
        return Contact.objects.filter(groups__in=self.groups.all())

    def send_preview(self):
        approval_message = "APPROVE? " + self.message
        self._send_batch(approval_message, self.previewcontacts.all())

    def _send_batch(self, message, contacts):
        vumiapi = VumiApi({'message_store': {}, 'message_sender': {}})
        tag = "default10001"
        batch_id = vumiapi.batch_start([tag])
        batch = MessageBatch(conversation=self, batch_id=batch_id)
        batch.save()
        addrs = [contact.msisdn for contact in contacts]
        msg_options = {"from_addr": tag}
        vumiapi.batch_send(batch_id, message, msg_options, addrs)

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
    conversation = models.ForeignKey(Conversation)
    batch_id = models.CharField(max_length=32)  # uuid4 as hex
