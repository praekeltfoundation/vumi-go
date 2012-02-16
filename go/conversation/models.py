from django.db import models
from django.conf import settings
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
        batch = self._send_batch(approval_message, self.previewcontacts.all())
        batch.preview_batch = self
        batch.save()
        # unit tests for start view
        # unit tests for start view with approved message

    def preview_status(self):
        vumiapi = self.vumi_api()
        batches = self.preview_batch_set.all()
        messages, replies = [], []
        for batch in batches:
            messages.extend(vumiapi.batch_messages(batch.batch_id))
            replies.extend(vumiapi.batch_replies(batch.batch_id))
        contacts = dict((c, 'waiting to send') for c in
                        self.previewcontacts.all())
        awaiting_reply = 'awaiting reply'
        for msg in messages:
            from_addr = msg['from_addr']
            if from_addr in contacts:
                contacts[from_addr] = awaiting_reply
        for reply in replies:
            from_addr = reply['from_addr']
            if from_addr in contacts and contacts[from_addr] == awaiting_reply:
                contents = reply['contents'].strip().lower()
                contacts[from_addr] = ('approved'
                                       if contents in ('approve', 'yes')
                                       else 'denied')
        return contacts

    def send_messages(self):
        batch = self._send_batch(self.message, self.people())
        batch.message_batch = self
        batch.save()

    @staticmethod
    def vumi_api():
        return VumiApi(settings.VUMI_API_CONFIG)

    def _send_batch(self, message, contacts):
        # ambient tags: default10001 - default11000 inclusive
        vumiapi = self.vumi_api()
        tag = vumiapi.acquire_tag("ambient")
        batch_id = vumiapi.batch_start([tag])
        batch = MessageBatch(batch_id=batch_id)
        batch.save()
        addrs = [contact.msisdn for contact in contacts]
        msg_options = {"from_addr": tag}
        vumiapi.batch_send(batch_id, message, msg_options, addrs)
        return batch

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
