# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Vumi API for high-volume messaging.

NOTE: This uses the synchronous RiakManager, and is therefore unsuitable for
use in Vumi workers.
"""

import redis
from datetime import datetime
from collections import defaultdict

from twisted.internet.defer import returnValue

from vumi.message import Message
from vumi.application import TagpoolManager
from vumi.persist.model import Manager
from vumi.persist.riak_manager import RiakManager
from vumi.persist.message_store import MessageStore
from vumi.middleware import TaggingMiddleware

from go.vumitools.account import AccountStore
from go.vumitools.contact import ContactStore
from go.vumitools.conversation import ConversationStore
from go.vumitools.middleware import DebitAccountMiddleware
from go.vumitools.credit import CreditManager


def get_redis(config):
    """Get a possibly fake redis."""
    redis_cls = config.get('redis_cls', redis.Redis)  # testing hook
    return redis_cls(**config.get('redis', {}))


class ConversationSendError(Exception):
    """Raised if there are no tags available for a given conversation."""


class ConversationWrapper(object):
    """Wrapper around a conversation, providing extended functionality.
    """

    def __init__(self, conversation, user_api):
        self.c = conversation
        self.user_api = user_api
        self.api = user_api.api
        self.mdb = self.api.mdb
        self.tpm = self.api.tpm
        self.manager = self.c.manager
        self.base_manager = self.api.manager
        self._tagpool_metadata = None

    @property
    def tagpool_metadata(self):
        if self._tagpool_metadata is None:
            self._tagpool_metadata = self.api.tpm.get_metadata(
                    self.delivery_tag_pool)
        return self._tagpool_metadata

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
        user_account = unicode(self.c.user_account.key)
        return self.mdb.batch_start([tag], user_account=user_account)

    def get_batches(self):
        return self.c.batches.get_all(self.base_manager)

    def get_batch_keys(self):
        return self.c.batches.keys()

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
            *delivery_report_delivered* The number of delivery reports
                    indicating successful delivery.
            *delivery_report_failed* The number of delivery reports
                    indicating failed delivery.
            *delivery_report_pending* The number of delivery reports
                    indicating ongoing attempts to deliver the message.
        """
        statuses = defaultdict(int)

        for batch_id in self.get_batch_keys():
            for k, v in self.mdb.batch_status(batch_id).items():
                k = k.replace('.', '_')
                statuses[k] += v
        total = len((yield self.people()))
        statuses.update({
            'total': total,
            'queued': total - statuses['sent'],
        })
        returnValue(dict(statuses))  # convert back from defaultdict

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
        returnValue(int(status['ack'] / float(status['total']) * 100))

    @Manager.calls_manager
    def start(self, **extra_params):
        """
        Send the start command to this conversations application worker.
        """
        tag = yield self.acquire_tag()
        batch_id = yield self.start_batch(tag)

        msg_options = {}
        # TODO: transport_type is probably irrelevant
        msg_options['transport_type'] = self.tagpool_metadata['transport_type']
        # TODO: not sure whether to declare that tag names must always be
        #       valid from_addr values or whether to put in a mapping somewhere
        msg_options['from_addr'] = tag[1]
        msg_options.update(self.tagpool_metadata.get('msg_options', {}))
        TaggingMiddleware.add_tag_to_payload(msg_options, tag)
        DebitAccountMiddleware.add_user_to_payload(msg_options,
                                                   self.c.user_account.key)

        yield self.dispatch_command('start',
            batch_id=batch_id,
            conversation_type=self.c.conversation_type,
            conversation_key=self.c.key,
            msg_options=msg_options,
            is_client_initiated=self.is_client_initiated(),
            **extra_params)
        self.c.batches.add_key(batch_id)
        yield self.c.save()

    @Manager.calls_manager
    def replies(self):
        """
        FIXME: this requires a contact to already exist in the database
                before it can show up as a reply. Isn't going to work
                for things like USSD and in some cases SMS.
        """
        batch_keys = self.get_batch_keys()
        reply_statuses = []
        replies = []
        for batch_id in batch_keys:
            # TODO: Not look up the batch by key again.
            replies.extend((yield self.mdb.batch_replies(batch_id)))
        for reply in replies:
            contact = yield self.user_api.contact_store.contact_for_addr(
                    self.delivery_class, reply['from_addr'])
            reply_statuses.append({
                'type': self.delivery_class,
                'source': self.delivery_class_description(),
                'contact': contact,
                'time': reply['timestamp'],
                'content': reply['content'],
                })
        returnValue(sorted(reply_statuses,
                           key=lambda reply: reply['time'],
                           reverse=True))

    @Manager.calls_manager
    def sent_messages(self):
        batch_keys = self.get_batch_keys()
        outbound_statuses = []
        messages = []
        for batch_id in batch_keys:
            # TODO: Not look up the batch by key again.
            messages.extend((yield self.mdb.batch_messages(batch_id)))
        for message in messages:
            contact = yield self.user_api.contact_store.contact_for_addr(
                    self.delivery_class, message['to_addr'])
            outbound_statuses.append({
                'type': self.delivery_class,
                'source': self.delivery_class_description(),
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

    def delivery_class_description(self):
        """
        FIXME: This actually returns the tagpool display name.
               The function itself is probably correct -- the
               name of the function is probably wrong.
        """
        return self.tagpool_metadata.get('display_name',
                                         self.delivery_tag_pool)

    def is_client_initiated(self):
        """
        Check whether this conversation can only be initiated by a client.

        :rtype: bool
        """
        return self.tagpool_metadata.get('client_initiated', False)

    def get_absolute_url(self):
        return u'/app/%s/%s/' % (self.conversation_type, self.key)


class TagpoolSet(object):
    """Holder for helper methods for retrieving tag pool information.

    :param dict pools:
        Dictionary of `tagpool name` -> `tagpool metadat` mappings.
    """

    # TODO: this should ideally need to be moved somewhere else
    #       but it's purely cosmetic so it can live here for now
    _DELIVERY_CLASS_NAMES = {
        'sms': 'SMS',
        'ussd': 'USSD',
        'gtalk': 'Gtalk',
        }

    def __init__(self, pools):
        self._pools = pools

    def select(self, filter_func):
        """Return a new :class:`TagpoolSet` that contains only pools
        that satisfy filter_func.

        :param function filter_func:
            A function f(pool, metadata) that should return True if the
            pool should be kept and False if it should be discarded.
        """
        new_pools = dict((pool, metadata)
                         for pool, metadata in self._pools.iteritems()
                         if filter_func(pool, metadata))
        return self.__class__(new_pools)

    def pools(self):
        return self._pools.keys()

    def tagpool_name(self, pool):
        return self._pools[pool].get('display_name', pool)

    def delivery_class(self, pool):
        return self._pools[pool].get('delivery_class', None)

    def delivery_classes(self):
        classes = set(self.delivery_class(pool) for pool in self.pools())
        classes.discard(None)
        return list(classes)

    def delivery_class_name(self, delivery_class):
        return self._DELIVERY_CLASS_NAMES.get(delivery_class, delivery_class)


class VumiUserApi(object):

    conversation_wrapper = ConversationWrapper

    def __init__(self, user_account_key, config, manager_cls=None):
        self.api = VumiApi(config, manager_cls=manager_cls)
        self.manager = self.api.manager
        self.user_account_key = user_account_key
        self.conversation_store = ConversationStore(self.api.manager,
                                                    self.user_account_key)
        self.contact_store = ContactStore(self.api.manager,
                                          self.user_account_key)

    def wrap_conversation(self, conversation):
        """Wrap a conversation with a ConversationWrapper.

        What it says on the tin, really.

        :param Conversation conversation:
            Conversation object to wrap.
        :rtype:
            ConversationWrapper.
        """
        return self.conversation_wrapper(conversation, self)

    def active_conversations(self):
        conversations = self.conversation_store.conversations
        return conversations.by_index(end_timestamp=None)

    @Manager.calls_manager
    def tagpools(self):
        account_store = self.api.account_store
        user_account = yield account_store.get_user(self.user_account_key)
        user_tagpools = yield user_account.tagpools.get_all()
        active_conversations = yield self.active_conversations()

        tp_usage = defaultdict(int)
        for conv in active_conversations:
            tp_usage[conv.delivery_tag_pool] += 1

        allowed_set = set(tp.tagpool for tp in user_tagpools
                          if (tp.max_keys is None
                              or tp.max_keys > tp_usage[tp.tagpool]))

        available_set = self.api.tpm.list_pools()
        pool_names = list(allowed_set & available_set)
        pool_data = dict((pool, self.api.tpm.get_metadata(pool))
                         for pool in pool_names)
        returnValue(TagpoolSet(pool_data))

    def list_groups(self):
        return sorted(self.contact_store.list_groups(),
            key=lambda group: group.name)

    def new_conversation(self, *args, **kw):
        return self.conversation_store.new_conversation(*args, **kw)


class VumiApi(object):
    def __init__(self, config, manager_cls=None):
        # TODO: Split the config up better.
        config = config.copy()  # So we can modify it.
        riak_config = config.pop('riak_manager')

        r_server = get_redis(config)

        if manager_cls is None:
            manager_cls = RiakManager
        self.manager = manager_cls.from_config(riak_config)

        # tagpool manager
        tpm_config = config.get('tagpool_manager', {})
        tpm_prefix = tpm_config.get('tagpool_prefix', 'tagpool_store')
        self.tpm = TagpoolManager(r_server, tpm_prefix)

        # credit manager
        cm_config = config.get('credit_manager', {})
        cm_prefix = cm_config.get('credit_prefix', 'credit_store')
        self.cm = CreditManager(r_server, cm_prefix)

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

    def set_pool_metadata(self, pool, metadata):
        """Set the metadata for a tag pool.

        :param str pool:
            Name of the pool set metadata form.
        :param dict metadata:
            Metadata to set.
        :rtype:
            None
        """
        return self.tpm.set_metadata(pool, metadata)

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
            'args': list(args),  # turn to list to make sure input & output
                                 # stay the same when encoded & decoded as
                                 # JSON.
            'kwargs': kwargs,
        })

    @classmethod
    def send(cls, batch_id, msg, msg_options, address):
        options = msg_options.copy()
        worker_name = options.pop('worker_name')
        return cls.command(worker_name, 'send', batch_id=batch_id,
            content=msg, to_addr=address, msg_options=options)
