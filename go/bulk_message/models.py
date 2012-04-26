import operator
import datetime
import redis

from django.db import models
from django.conf import settings

from go.contacts.models import Contact
from go.vumitools import VumiApi


redis = redis.Redis(**settings.VXPOLLS_REDIS_CONFIG)


def get_tag_pool_names():
    pool_names = []
    for delivery_class, tag_pools in get_combined_delivery_classes():
        for tag_pool, label in tag_pools:
            pool_names.append(tag_pool)
    return pool_names

def get_server_init_tag_pool_names():
    pool_names = []
    for delivery_class, tag_pools in get_server_init_delivery_classes():
        for tag_pool, label in tag_pools:
            pool_names.append(tag_pool)
    return pool_names

def get_delivery_class_names():
    return [delivery_class for delivery_class, tag_pools
                in get_combined_delivery_classes()]

def get_combined_delivery_classes():
    return (get_client_init_delivery_classes() +
                get_server_init_delivery_classes())

def get_server_init_delivery_class_names():
    return [delivery_class for delivery_class, tag_pools
                in get_server_init_delivery_classes()]

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
    delivery_tag_pool = models.CharField(max_length=255, null=True)

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

    def is_client_initiated(self):
        return (self.delivery_class not in
                    get_server_init_delivery_class_names())

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

    def get_status(self):
        if self.ended():
            return CONVERSATION_FINISHED
        elif self.message_batch_set.exists():
            return CONVERSATION_RUNNING
        else:
            return CONVERSATION_RUNNING

    def get_tags(self):
        if self.get_status() == CONVERSATION_RUNNING:
            batch = self.message_batch_set.latest('pk')
            vumiapi = self.vumi_api()
            tags = vumiapi.batch_tags(batch.batch_id)
            return tags

    def get_progress_status(self):
        default = {
            'total': 0,
            'queued': 0,
            'ack': 0,
            'sent': 0,
            'delivery_report': 0,
        }

        vumiapi = self.vumi_api()
        batch = self.message_batch_set.latest('pk')
        default.update(vumiapi.mdb.batch_status(batch.batch_id))
        total = self.people().count()
        default.update({
            'total': total,
            'queued': total - default['sent'],
        })
        return default

    def get_progress_percentage(self):
        status = self.get_progress_status()
        if self.people().exists():
            return int(status['ack'] / float(status['total'])) * 100
        return 0

    def send_messages(self):
        batch = self._send_batch(
            self.delivery_class, self.message, self.people())
        batch.message_batch = self
        batch.save()

    def start_survey(self):
        batch = self._send_batch(
            self.delivery_class, '', self.people()
        )
        batch.message_batch = self
        batch.save()

    def delivery_class_description(self):
        delivery_classes = dict(get_combined_delivery_classes())
        tag_pools = dict(delivery_classes.get(self.delivery_class))
        description = tag_pools.get(self.delivery_tag_pool)
        if description is None:
            description = "Unknown"
        return description

    def replies(self):
        batches = self.message_batch_set.all()
        reply_statuses = []
        for contact, reply in self._get_replies(self.delivery_class, batches):
            delivery_classes = dict(get_combined_delivery_classes())
            tag_pools = dict(delivery_classes.get(self.delivery_class))
            reply_statuses.append({
                'type': self.delivery_class,
                'source': tag_pools.get(self.delivery_tag_pool, 'Unknown'),
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
            delivery_classes = dict(get_combined_delivery_classes())
            outbound_statuses.append({
                'type': self.delivery_class,
                'source': delivery_classes.get(self.delivery_class, 'Unknown'),
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
        if delivery_class == "shortcode":
            return "shortcode", "sms"
        elif delivery_class == "longcode":
            return "longcode", "sms"
        elif delivery_class == "xmpp":
            return "xmpp", "xmpp"
        elif delivery_class == "gtalk":
            return "xmpp", "xmpp"
        elif delivery_class == "sms":
            return "longcode", "sms"
        elif delivery_class == "ussd":
            return "truteq", "ussd"
        else:
            raise ConversationSendError("Unknown delivery class %r"
                                        % (delivery_class,))

    def tag_message_options(self, tagpool, tag):
        """Return message options for tagpool and tag."""
        # TODO: this is hardcoded for ambient and gtalk pool currently
        if tagpool == "shortcode":
            return {
                "from_addr": tag[1],
                "transport_name": "smpp_transport",
                "transport_type": "sms",
            }
        elif tagpool == "longcode":
            return {
                "from_addr": tag[1],
                "transport_name": "smpp_transport",
                "transport_type": "sms",
            }
        elif tagpool == "xmpp":
            return {
                "from_addr": tag[1],
                "transport_name": "gtalk_vumigo",
                "transport_type": "xmpp",
            }
        elif tagpool == "truteq":
            return {
                "from_addr": tag[1],
                "transport_name": "truteq_transport",
                "transport_type": "ussd",
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
        print 'getting for', tagpool, transport_type
        addrs = [contact.addr_for(transport_type) for contact in contacts]
        addrs = [addr for addr in addrs if addr]
        tag = vumiapi.acquire_tag(tagpool)
        if tag is None:
            raise ConversationSendError("No spare messaging tags.")
        msg_options = self.tag_message_options(tagpool, tag)
        # Add the worker_name so our command dispatcher knows where
        # to send stuff to.
        msg_options.update({
            'worker_name': '%s_application' % (self.conversation_type,),
            'conversation_id': self.pk,
            'conversation_type': self.conversation_type,
        })
        batch_id = vumiapi.batch_start([tag])
        batch = MessageBatch(batch_id=batch_id)
        batch.save()
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
                except (Contact.DoesNotExist,
                        Contact.MultipleObjectsReturned), e:
                    print e
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

    @models.permalink
    def get_absolute_url(self):
        return ('%ss:show' % (self.conversation_type,), (self.pk,))


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

    def __unicode__(self):
        return u"<MessageBatch: %s>" % (self.batch_id,)


class ConversationSendError(Exception):
    """Raised if there are no tags available for a given conversation."""
