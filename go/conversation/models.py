import operator
import datetime
import redis

from django.db import models
from django.conf import settings

from go.contacts.models import Contact
from go.vumitools import VumiApi
from go.vumitools.api import VumiApiCommand


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

    def is_client_initiated(self):
        """
        Check whether this conversation can only be initiated by a client.

        :rtype: bool
        """
        return (self.delivery_class not in
                    get_server_init_delivery_class_names())

    def get_status(self):
        """
        Get the status of this conversation

        :rtype: str, (CONVERSATION_FINISHED, CONVERSATION_RUNNING, or
            CONVERSATION_DRAFT)

        """
        if self.ended():
            return CONVERSATION_FINISHED
        elif self.message_batch_set.exists():
            return CONVERSATION_RUNNING
        else:
            return CONVERSATION_DRAFT

    def get_tags(self):
        """
        Return any tags associated with this conversation.

        :rtype:
            Returns a list of tags `[(tagpool, tag), ... ]`
        """
        tags = []
        vumiapi = self.vumi_api()
        for batch in self.message_batch_set.all():
            tags.extend(vumiapi.batch_tags(batch.batch_id))
        return tags

    def get_progress_status(self):
        """
        Get an overview of the progress of this conversation

        :rtype: dict
            *total* The number of messages in this conversation.
            *sent* The number of messages sent.
            *queued* The number of messages yet to be sent out.
            *ack* The number of messages that have been acknowledged
                    by the network for delivery
            *delivery_report* The number of messages we've received
                    a delivery report for.
        """
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
        """
        Get a percentage indication of how far along the sending
        of messages in this conversation is.

        :rtype: int
        """
        status = self.get_progress_status()
        if self.people().exists():
            return int(status['ack'] / float(status['total'])) * 100
        return 0

    def get_contacts_addresses(self, delivery_class=None):
        """
        Get the contacts assigned to this group with an address attribute
        that is appropriate for the given delivery_class

        :rtype: str
        :param rtype: the name of the delivery class to use, if None then
                    it will default to `self.delivery_class`
        """
        delivery_class = delivery_class or self.delivery_class
        addrs = [contact.addr_for(delivery_class) for contact
                    in self.people().all()]
        return [addr for addr in addrs if addr]

    def start(self):
        """
        Send the start command to this conversations application worker.
        """
        tag = self.acquire_tag()
        batch_id = self.start_batch(tag)

        self.dispatch_command('start',
            batch_id=batch_id,
            conversation_type=self.conversation_type,
            conversation_id=self.pk,
            msg_options={
                'transport_type': self.delivery_class,
                'from_addr': tag[1],
            })

        batch = MessageBatch.objects.create(batch_id=batch_id,
                                                message_batch=self)
        batch.save()

    def delivery_class_description(self):
        """
        FIXME: this is a hack
        """
        delivery_classes = dict(get_combined_delivery_classes())
        tag_pools = dict(delivery_classes.get(self.delivery_class))
        description = tag_pools.get(self.delivery_tag_pool)
        if description is None:
            description = "Unknown"
        return description

    def replies(self):
        """
        FIXME: this requires a contact to already exist in the database
                before it can show up as a reply. Isn't going to work
                for things like USSD and in some cases SMS.
        """
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

    def dispatch_command(self, command, *args, **kwargs):
        """
        Send a command to the GoApplication worker listening to this
        conversation type's worker name. The *args and **kwargs
        are expanded when the command is called.

        :type command: str
        :params command:
            The name of the command to call
        """
        vumiapi = self.vumi_api()
        worker_name = '%s_application' % (self.conversation_type,)
        command = VumiApiCommand.command(worker_name, command, *args, **kwargs)
        return vumiapi.send_command(command)

    def acquire_tag(self, pool=None):
        vumiapi = self.vumi_api()
        tag = vumiapi.acquire_tag(pool or self.delivery_tag_pool)
        if tag is None:
            raise ConversationSendError("No spare messaging tags.")
        return tag

    def start_batch(self, tag):
        vumiapi = self.vumi_api()
        return vumiapi.batch_start([tag])

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

        replies = []
        for batch in batches:
            for reply in batch_msg_func(batch.batch_id):
                try:
                    contact = Contact.for_addr(self.user, self.delivery_class,
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
        return ('%s:show' % (self.conversation_type,), (self.pk,))


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
