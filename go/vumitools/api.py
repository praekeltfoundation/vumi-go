# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Vumi API for high-volume messaging.

NOTE: This uses the synchronous RiakManager, and is therefore unsuitable for
use in Vumi workers.
"""

import redis
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.message import Message
from vumi.application import TagpoolManager
from vumi.persist.model import Manager
from vumi.persist.riak_manager import RiakManager
from vumi.persist.message_store import MessageStore

from go.vumitools.account import AccountStore
from go.vumitools.contact import ContactStore
from go.vumitools.conversation import get_combined_delivery_classes


def get_redis(config):
    """Get a possibly fake redis."""
    redis_cls = config.get('redis_cls', redis.Redis)  # testing hook
    return redis_cls(**config.get('redis', {}))


class ConversationSendError(Exception):
    """Raised if there are no tags available for a given conversation."""


class ConversationWrapper(object):
    """Wrapper around a conversation, providing extended functionality.
    """

    def __init__(self, conversation, api):
        self.c = conversation
        self.api = api
        self.mdb = api.mdb
        self.tpm = api.tpm
        self.manager = self.c.manager
        self.base_manager = self.api.manager
        self.contact_store = ContactStore(self.base_manager,
                                          self.c.user_account.key)

    @Manager.calls_manager
    def end_conversation(self):
        self.c.end_timestamp = datetime.utcnow()
        yield self.c.save()
        yield self._release_batches()

    @Manager.calls_manager
    def _release_batches(self):
        for batch in (yield self.get_batches()):
            yield self.mdb.batch_done(batch.key)  # TODO: why key?
            for tag in batch.tags:
                yield self.tpm.release_tag(tag)

    def __getattr__(self, name):
        # Proxy anything we don't have back to the wrapped conversation.
        return getattr(self.c, name)

    # TODO: Something about setattr?

    def start_batch(self, tag):
        return self.mdb.batch_start([tag])

    def get_batches(self):
        return self.c.batches.get_all(self.base_manager)

    @Manager.calls_manager
    def get_tags(self):
        """
        Return any tags associated with this conversation.

        :rtype:
            Returns a list of tags `[(tagpool, tag), ... ]`
        """
        tags = []
        for batch in (yield self.get_batches()):
            tags.extend((yield batch.tags))
        returnValue(tags)

    @Manager.calls_manager
    def people(self):
        people = []
        for group in (yield self.c.groups.get_all()):
            people.extend((yield group.backlinks.contacts()))
        returnValue(people)

    @Manager.calls_manager
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

        for batch in (yield self.c.batches.get_all()):
            for k, v in (yield self.mdb.batch_status(batch.key)):
                default[k] += v
        total = len((yield self.people()))
        default.update({
            'total': total,
            'queued': total - default['sent'],
        })
        returnValue(default)

    @Manager.calls_manager
    def get_progress_percentage(self):
        """
        Get a percentage indication of how far along the sending
        of messages in this conversation is.

        :rtype: int
        """
        status = yield self.get_progress_status()
        if status['total'] == 0:
            returnValue(0)
        returnValue(int(status['ack'] / float(status['total'])) * 100)

    @Manager.calls_manager
    def get_contacts_addresses(self, delivery_class=None):
        """
        Get the contacts assigned to this group with an address attribute
        that is appropriate for the given delivery_class

        :rtype: str
        :param rtype: the name of the delivery class to use, if None then
                    it will default to `self.delivery_class`
        """
        delivery_class = delivery_class or self.c.delivery_class
        addrs = [contact.addr_for(delivery_class)
                 for contact in (yield self.people())]
        returnValue([addr for addr in addrs if addr])

    @Manager.calls_manager
    def start(self):
        """
        Send the start command to this conversations application worker.
        """
        tag = yield self.acquire_tag()
        batch_id = yield self.start_batch(tag)

        yield self.dispatch_command('start',
            batch_id=batch_id,
            conversation_type=self.c.conversation_type,
            conversation_id=self.c.key,
            msg_options={
                'transport_type': self.c.delivery_class,
                'from_addr': tag[1],
            })
        self.c.batches.add_key(batch_id)
        yield self.c.save()

    @Manager.calls_manager
    def replies(self):
        """
        FIXME: this requires a contact to already exist in the database
                before it can show up as a reply. Isn't going to work
                for things like USSD and in some cases SMS.
        """
        batches = yield self.get_batches()
        reply_statuses = []
        replies = []
        for batch in batches:
            # TODO: Not look up the batch by key again.
            replies.extend((yield self.mdb.batch_replies(batch.key)))
        for reply in replies:
            contact = yield self.contact_store.contact_for_addr(
                    self.delivery_class, reply['from_addr'])
            delivery_classes = dict(get_combined_delivery_classes())
            tag_pools = dict(delivery_classes.get(self.delivery_class))
            reply_statuses.append({
                'type': self.delivery_class,
                'source': tag_pools.get(self.delivery_tag_pool, 'Unknown'),
                'contact': contact,
                'time': reply['timestamp'],
                'content': reply['content'],
                })
        returnValue(sorted(reply_statuses,
                           key=lambda reply: reply['time'],
                           reverse=True))

    @Manager.calls_manager
    def sent_messages(self):
        batches = yield self.get_batches()
        outbound_statuses = []
        messages = []
        for batch in batches:
            # TODO: Not look up the batch by key again.
            messages.extend((yield self.mdb.batch_messages(batch.key)))
        for message in messages:
            contact = yield self.contact_store.contact_for_addr(
                    self.delivery_class, message['to_addr'])
            delivery_classes = dict(get_combined_delivery_classes())
            outbound_statuses.append({
                'type': self.delivery_class,
                'source': delivery_classes.get(self.delivery_class, 'Unknown'),
                'contact': contact,
                'time': message['timestamp'],
                'content': message['content']
                })
        returnValue(sorted(outbound_statuses, key=lambda sent: sent['time'],
                           reverse=True))

    @Manager.calls_manager
    def acquire_tag(self, pool=None):
        tag = yield self.api.acquire_tag(pool or self.delivery_tag_pool)
        if tag is None:
            raise ConversationSendError("No spare messaging tags.")
        returnValue(tag)

    def dispatch_command(self, command, *args, **kwargs):
        """
        Send a command to the GoApplication worker listening to this
        conversation type's worker name. The *args and **kwargs
        are expanded when the command is called.

        :type command: str
        :params command:
            The name of the command to call
        """
        worker_name = '%s_application' % (self.conversation_type,)
        command = VumiApiCommand.command(worker_name, command, *args, **kwargs)
        return self.api.send_command(command)


class VumiApi(object):
    conversation_wrapper = ConversationWrapper

    def __init__(self, config):
        # TODO: Split the config up better.
        config = config.copy()  # So we can modify it.
        riak_config = config.pop('riak_manager')

        r_server = get_redis(config)
        self.manager = RiakManager.from_config(riak_config)

        # tagpool manager
        tpm_config = config.get('tagpool_manager', {})
        tpm_prefix = tpm_config.get('tagpool_prefix', 'tagpool_store')
        self.tpm = TagpoolManager(r_server, tpm_prefix)

        # message store
        mdb_config = config.get('message_store', {})
        mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        self.mdb = MessageStore(self.manager, r_server, mdb_prefix)

        # account store
        self.account_store = AccountStore(self.manager)

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

    def wrap_conversation(self, conversation):
        """Wrap a conversation with a ConversationWrapper.

        What it says on the tin, really.

        :param Conversation conversation:
            Conversation object to wrap.
        :rtype:
            ConversationWrapper.
        """
        return self.conversation_wrapper(conversation, self)


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
