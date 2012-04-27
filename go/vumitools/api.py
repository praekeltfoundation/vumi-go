# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Vumi API for high-volume messaging.

NOTE: This uses the synchronous RiakManager, and is therefore unsuitable for
use in Vumi workers.
"""

import redis

from vumi.message import Message

from vumi.application import TagpoolManager
from vumi.persist.riak_manager import RiakManager
from vumi.persist.message_store import MessageStore


def get_redis(config):
    """Get a possibly fake redis."""
    redis_cls = config.get('redis_cls', redis.Redis)  # testing hook
    return redis_cls(**config.get('redis', {}))


class VumiApi(object):

    def __init__(self, config):
        config = config.copy()  # So we can modify it.
        riak_config = config.pop('riak_manager')
        r_server = get_redis(config)

        # tagpool manager
        tpm_config = config.get('tagpool_manager', {})
        tpm_prefix = tpm_config.get('tagpool_prefix', 'tagpool_store')
        self.tpm = TagpoolManager(r_server, tpm_prefix)
        # message store
        mdb_config = config.get('message_store', {})
        mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        self.manager = RiakManager.from_config(riak_config)
        self.mdb = MessageStore(self.manager, r_server, mdb_prefix)
        # message sending API
        mapi_config = config.get('message_sender', {})
        self.mapi = MessageSender(mapi_config)

    def batch_start(self, tags):
        """Start a message batch.

        :type tags: list of str
        :param tags:
            A list of identifiers for linking replies to this
            batch. Conceptually a tag corresponds to a set of
            from_addrs that a message goes out on. The from_addrs can
            then be observed in incoming messages and used to link
            replies to a specific batch.
        :rtype:
            Returns the batch_id of the new batch.
        """
        return self.mdb.batch_start(tags)

    def batch_done(self, batch_id):
        """Mark a batch as completed.

        Once a batch is done, inbound messages will not be mapped
        to it.

        :type batch_id: str
        :param batch_id:
            batch to mark as done.
        :rtype:
            None.
        """
        return self.mdb.batch_done(batch_id)

    def send_command(self, command):
        """Send a command to the GoApplication via the control
        channel.

        :type command: VumiApiCommand
        :param command:
            The command to send
        :rtype:
            None.
        """
        self.mapi.send_command(command)

    def batch_send(self, batch_id, msg, msg_options, addresses):
        """Send a batch of text message to a list of addresses.

        Use multiple calls to :meth:`batch_send` if you have *lots* of
        addresses and don't want to pass them all in one API
        call. Messages passed to multiple calls to :meth:`batch_send`
        do not have to be the same.

        :type batch_id: str
        :param batch_id:
            batch to append the messages too
        :type msg: unicode
        :param msg:
            text to send
        :type msg_options: dict
        :param msg_options:
            additional paramters for the outgoing Vumi message, usually
            something like {'from_addr': '+1234'} or {}.
        :type addresses:
        :param msg:
            list of addresses to send messages to
        :rtype:
            None.
        """
        for address in addresses:
            command = VumiApiCommand.send(batch_id, msg, msg_options, address)
            self.send_command(command)

    def batch_status(self, batch_id):
        """Check the status of a batch of messages.

        :type batch_id: str
        :param batch_id:
            batch to check the status of
        :rtype:
            dictionary of counts of messages in batch,
            messages sent, messages acked and messages
            with delivery reports.
        """
        return self.mdb.batch_status(batch_id)

    def batch_messages(self, batch_id):
        """Return a list of batch message dictionaries.

        Should only be used on batches that are expected
        to have a small set of messages.

        :type batch_id: str
        :param batch_id:
            batch to get messages for
        :rtype:
            list of message dictionaries.
        """
        return self.mdb.batch_messages(batch_id)

    def batch_replies(self, batch_id):
        """Return a list of reply message dictionaries.

        Should only be used on batches that are expected
        to have a small set of replies.

        :type batch_id: str
        :param batch_id:
            batch to get replies for
        :rtype:
            list of message dictionaries.
        """
        return self.mdb.batch_replies(batch_id)

    def batch_tags(self, batch_id):
        """Return a list of tags associated with a given batch.

        :type batch_id: str
        :param batch_id:
            batch to get tags for
        :rtype:
            list of tags
        """
        return list(self.mdb.get_batch(batch_id).tags)

    def acquire_tag(self, pool):
        """Acquire a tag from a given tag pool.

        Tags should be held for the duration of a conversation.

        :type pool: str
        :param pool:
            name of the pool to retrieve tags from.
        :rtype:
            str containing the tag
        """
        return self.tpm.acquire_tag(pool)

    def release_tag(self, tag):
        """Release a tag back to the pool it came from.

        Tags should be released only once a conversation is finished.

        :type pool: str
        :param pool:
            name of the pool to return the tag too (must be the same as
            the name of the pool the tag came from).
        :rtype:
            None.
        """
        return self.tpm.release_tag(tag)

    def declare_tags(self, tags):
        """Populate a pool with tags.

        Tags already in the pool are not duplicated.

        :type pool: str
        :type tags: list of (pool, local_tag) tuples
        :param tags:
            list of tags to add to the pool.
        :rtype:
            None
        """
        return self.tpm.declare_tags(tags)

    def purge_pool(self, pool):
        """Completely remove a pool with all its contents.

        If tags in the pool are still in use it will throw an error.

        :type pool: str
        :param pool:
            name of the pool to purge.
        :rtype:
            None.
        """
        return self.tpm.purge_pool(pool)

    ### Conversation stuff.

    # def send_preview(self, conv):
    #     approval_message = "APPROVE? " + conv.message
    #     batch = self._send_batch(
    #         conv.delivery_class, approval_message,
    #         conv.previewcontacts.get_all())
    #     batch.preview_batch = self
    #     batch.save()

    # def send_messages(self):
    #     batch = self._send_batch(
    #         self.delivery_class, self.message, self.people())
    #     batch.message_batch = self
    #     batch.save()

    # def start_survey(self):
    #     batch = self._send_batch(
    #         self.delivery_class, '', self.people()
    #     )
    #     batch.message_batch = self
    #     batch.save()

    # def delivery_class_description(self):
    #     delivery_classes = dict(get_delivery_classes())
    #     description = delivery_classes.get(self.delivery_class)
    #     if description is None:
    #         description = "Unknown"
    #     return description

    # def replies(self):
    #     batches = self.message_batch_set.all()
    #     reply_statuses = []
    #     for contact, reply in self._get_replies(self.delivery_class, batches):
    #         delivery_classes = dict(get_delivery_classes())
    #         reply_statuses.append({
    #             'type': self.delivery_class,
    #             'source': delivery_classes.get(self.delivery_class, 'Unknown'),
    #             'contact': contact,
    #             'time': reply['timestamp'],
    #             'content': reply['content'],
    #             })
    #     return sorted(reply_statuses, key=lambda reply: reply['time'],
    #                     reverse=True)

    # def sent_messages(self):
    #     batches = self.message_batch_set.all()
    #     outbound_statuses = []
    #     sent_messages = self._get_messages(self.delivery_class, batches)
    #     for contact, message in sent_messages:
    #         delivery_classes = dict(get_delivery_classes())
    #         outbound_statuses.append({
    #             'type': self.delivery_class,
    #             'source': delivery_classes.get(self.delivery_class, 'Unknown'),
    #             'contact': contact,
    #             'time': message['timestamp'],
    #             'content': message['content']
    #             })
    #     return sorted(outbound_statuses, key=lambda sent: sent['time'],
    #                     reverse=True)

    # @staticmethod
    # def vumi_api():
    #     return VumiApi(settings.VUMI_API_CONFIG)

    # def delivery_info(self, delivery_class):
    #     """Return a delivery information for a given delivery_class."""
    #     # TODO: remove hard coded delivery class to tagpool and transport_type
    #     #       mapping
    #     if delivery_class == "shortcode":
    #         return "shortcode", "sms"
    #     elif delivery_class == "longcode":
    #         return "longcode", "sms"
    #     elif delivery_class == "xmpp":
    #         return "xmpp", "xmpp"
    #     elif delivery_class == "gtalk":
    #         return "xmpp", "xmpp"
    #     elif delivery_class == "sms":
    #         return "longcode", "sms"
    #     else:
    #         raise ConversationSendError("Unknown delivery class %r"
    #                                     % (delivery_class,))

    # def tag_message_options(self, tagpool, tag):
    #     """Return message options for tagpool and tag."""
    #     # TODO: this is hardcoded for ambient and gtalk pool currently
    #     if tagpool == "shortcode":
    #         return {
    #             "from_addr": tag[1],
    #             "transport_name": "smpp_transport",
    #             "transport_type": "sms",
    #         }
    #     elif tagpool == "longcode":
    #         return {
    #             "from_addr": tag[1],
    #             "transport_name": "smpp_transport",
    #             "transport_type": "sms",
    #         }
    #     elif tagpool == "xmpp":
    #         return {
    #             "from_addr": tag[1],
    #             "transport_name": "gtalk_vumigo",
    #             "transport_type": "xmpp",
    #         }
    #     else:
    #         raise ConversationSendError("Unknown tagpool %r" % (tagpool,))

    # def _send_batch(self, delivery_class, message, contacts):
    #     if delivery_class is None:
    #         raise ConversationSendError("No delivery class specified.")
    #     if self.ended():
    #         raise ConversationSendError("Conversation has already ended --"
    #                                     " no more messages may be sent.")
    #     vumiapi = self.vumi_api()
    #     tagpool, transport_type = self.delivery_info(delivery_class)
    #     addrs = [contact.addr_for(transport_type) for contact in contacts]
    #     addrs = [addr for addr in addrs if addr]
    #     tag = vumiapi.acquire_tag(tagpool)
    #     if tag is None:
    #         raise ConversationSendError("No spare messaging tags.")
    #     msg_options = self.tag_message_options(tagpool, tag)
    #     # Add the worker_name so our command dispatcher knows where
    #     # to send stuff to.
    #     msg_options.update({
    #         'worker_name': '%s_application' % (self.conversation_type,),
    #         'conversation_id': self.pk,
    #         'conversation_type': self.conversation_type,
    #     })
    #     batch_id = vumiapi.batch_start([tag])
    #     batch = MessageBatch(batch_id=batch_id)
    #     batch.save()
    #     vumiapi.batch_send(batch_id, message, msg_options, addrs)
    #     return batch

    # def _release_preview_tags(self):
    #     self._release_batches(self.preview_batch_set.all())

    # def _release_message_tags(self):
    #     self._release_batches(self.message_batch_set.all())

    # def _release_batches(self, batches):
    #     vumiapi = self.vumi_api()
    #     for batch in batches:
    #         vumiapi.batch_done(batch.batch_id)
    #         for tag in vumiapi.batch_tags(batch.batch_id):
    #             vumiapi.release_tag(tag)

    # def _release_tags(self):
    #     self._release_preview_tags()
    #     self._release_message_tags()

    # def _get_replies(self, delivery_class, batches):
    #     vumiapi = self.vumi_api()
    #     addr_func = operator.itemgetter('from_addr')
    #     batch_msg_func = vumiapi.batch_replies
    #     return self._get_helper(delivery_class, batches,
    #                             addr_func, batch_msg_func)

    # @Manager.calls_manager
    # def preview_status(self, conversation):
    #     batches = yield conversation.preview_batches.get_all()
    #     messages = self._get_messages(self.delivery_class, batches)
    #     replies = self._get_replies(self.delivery_class, batches)
    #     contacts = dict((c, 'waiting to send') for c in
    #                     self.previewcontacts.all())
    #     awaiting_reply = 'awaiting reply'
    #     for contact, msg in messages:
    #         if contact in contacts:
    #             contacts[contact] = awaiting_reply
    #     for contact, reply in replies:
    #         if contact in contacts and contacts[contact] == awaiting_reply:
    #             contents = (reply['content'] or '').strip().lower()
    #             contacts[contact] = ('approved'
    #                                  if contents in ('approve', 'yes')
    #                                  else 'denied')
    #             if contacts[contact] == 'approved':
    #                 self._release_preview_tags()
    #     return sorted(contacts.items())

    # @Manager.calls_manager
    # def _get_messages(self, delivery_class, batches):
    #     vumiapi = self.vumi_api()
    #     addr_func = operator.itemgetter('to_addr')
    #     batch_msg_func = vumiapi.batch_messages
    #     return self._get_helper(delivery_class, batches,
    #                             addr_func, batch_msg_func)

    # def _get_helper(self, delivery_class, batches, addr_func, batch_msg_func):
    #     """Return a list of (Contact, reply_msg) tuples."""
    #     if delivery_class is None:
    #         return []
    #     _tagpool, transport_type = self.delivery_info(delivery_class)

    #     replies = []
    #     for batch in batches:
    #         for reply in batch_msg_func(batch.batch_id):
    #             try:
    #                 contact = Contact.for_addr(self.user, transport_type,
    #                                            addr_func(reply))
    #             except (Contact.DoesNotExist,
    #                     Contact.MultipleObjectsReturned), e:
    #                 print e
    #                 continue
    #             replies.append((contact, reply))
    #     return replies


class MessageSender(object):
    def __init__(self, config):
        from go.vumitools import api_celery
        self.config = config
        self.sender_api = api_celery
        self.publisher_config = VumiApiCommand.default_routing_config()

    def send_command(self, command):
        self.sender_api.send_command_task.delay(command, self.publisher_config)


class VumiApiCommand(Message):

    _DEFAULT_ROUTING_CONFIG = {
        'exchange': 'vumi',
        'exchange_type': 'direct',
        'routing_key': 'vumi.api',
        }

    @classmethod
    def default_routing_config(cls):
        return cls._DEFAULT_ROUTING_CONFIG.copy()

    @classmethod
    def command(cls, worker_name, command_name, *args, **kwargs):
        return cls(**{
            'worker_name': worker_name,
            'command': command_name,
            'args': args,
            'kwargs': kwargs,
        })

    @classmethod
    def send(cls, batch_id, msg, msg_options, address):
        options = msg_options.copy()
        worker_name = options.pop('worker_name')
        return cls.command(worker_name, 'send', batch_id=batch_id,
            content=msg, to_addr=address, msg_options=options)
