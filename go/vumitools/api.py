# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Convenience API, mostly for working with various datastores."""

from collections import defaultdict

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.errors import VumiError
from vumi.service import Publisher
from vumi.message import Message
from vumi.components.tagpool import TagpoolManager
from vumi.components.message_store import MessageStore
from vumi.persist.model import Manager
from vumi.persist.riak_manager import RiakManager
from vumi.persist.txriak_manager import TxRiakManager
from vumi.persist.redis_manager import RedisManager
from vumi.persist.txredis_manager import TxRedisManager

from go.vumitools.account import AccountStore
from go.vumitools.contact import ContactStore
from go.vumitools.conversation import ConversationStore
from go.vumitools.conversation.utils import ConversationWrapper
from go.vumitools.credit import CreditManager

from django.conf import settings
from django.utils.datastructures import SortedDict


class TagpoolSet(object):
    """Holder for helper methods for retrieving tag pool information.

    :param dict pools:
        Dictionary of `tagpool name` -> `tagpool metadata` mappings.
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

    def display_name(self, pool):
        return self._pools[pool].get('display_name', pool)

    def user_selects_tag(self, pool):
        return self._pools[pool].get('user_selects_tag', False)

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

    def __init__(self, api, user_account_key):
        self.api = api
        self.manager = self.api.manager
        self.user_account_key = user_account_key
        self.conversation_store = ConversationStore(self.api.manager,
                                                    self.user_account_key)
        self.contact_store = ContactStore(self.api.manager,
                                          self.user_account_key)

    @classmethod
    def from_config_sync(cls, user_account_key, config):
        return cls(VumiApi.from_config_sync(config), user_account_key)

    @classmethod
    def from_config_async(cls, user_account_key, config):
        d = VumiApi.from_config_async(config)
        return d.addCallback(cls, user_account_key)

    def wrap_conversation(self, conversation):
        """Wrap a conversation with a ConversationWrapper.

        What it says on the tin, really.

        :param Conversation conversation:
            Conversation object to wrap.
        :rtype:
            ConversationWrapper.
        """
        return self.conversation_wrapper(conversation, self)

    @Manager.calls_manager
    def get_wrapped_conversation(self, conversation_key):
        conversation = yield self.conversation_store.get_conversation_by_key(
            conversation_key)
        if conversation:
            returnValue(self.wrap_conversation(conversation))

    @Manager.calls_manager
    def active_conversations(self):
        conversations = self.conversation_store.conversations
        keys = yield conversations.index_lookup(
            'end_timestamp', None).get_keys()
        # NOTE: This assumes that we don't have very large numbers of active
        #       conversations.
        convs = []
        for convs_bunch in conversations.load_all_bunches(keys):
            convs.extend((yield convs_bunch))
        returnValue(convs)

    @Manager.calls_manager
    def running_conversations(self):
        conversations = yield self.active_conversations()
        returnValue([c for c in conversations if c.running()])

    @Manager.calls_manager
    def tagpools(self):
        account_store = self.api.account_store
        user_account = yield account_store.get_user(self.user_account_key)
        active_conversations = yield self.active_conversations()

        tp_usage = defaultdict(int)
        for conv in active_conversations:
            tp_usage[conv.delivery_tag_pool] += 1

        allowed_set = set()
        for tp_bunch in user_account.tagpools.load_all_bunches():
            for tp in (yield tp_bunch):
                if (tp.max_keys is None
                        or tp.max_keys > tp_usage[tp.tagpool]):
                    allowed_set.add(tp.tagpool)

        available_set = yield self.api.tpm.list_pools()
        pool_names = list(allowed_set & available_set)
        pool_data = dict([(pool, (yield self.api.tpm.get_metadata(pool)))
                         for pool in pool_names])
        returnValue(TagpoolSet(pool_data))

    @Manager.calls_manager
    def applications(self):
        account_store = self.api.account_store
        user_account = yield account_store.get_user(self.user_account_key)
        # NOTE: This assumes that we don't have very large numbers of
        #       applications.
        applications = []
        for permissions in user_account.applications.load_all_bunches():
            applications.extend((yield permissions))
        app_settings = settings.VUMI_INSTALLED_APPS
        returnValue(SortedDict([(application,
                        app_settings[application])
                        for application in sorted(applications)
                        if application in app_settings]))

    def list_groups(self):
        return sorted(self.contact_store.list_groups(),
            key=lambda group: group.name)

    def new_conversation(self, *args, **kw):
        return self.conversation_store.new_conversation(*args, **kw)


class VumiApi(object):
    def __init__(self, manager, redis, sender=None):
        self.manager = manager
        self.redis = redis

        self.tpm = TagpoolManager(self.redis.sub_manager('tagpool_store'))
        self.cm = CreditManager(self.redis.sub_manager('credit_store'))
        self.mdb = MessageStore(self.manager,
                                self.redis.sub_manager('message_store'))
        self.account_store = AccountStore(self.manager)
        self.mapi = sender

    @staticmethod
    def _parse_config(config):
        riak_config = config.get('riak_manager', {})
        redis_config = config.get('redis_manager', {})
        return riak_config, redis_config

    @classmethod
    def from_config_sync(cls, config):
        riak_config, redis_config = cls._parse_config(config)
        manager = RiakManager.from_config(riak_config)
        redis = RedisManager.from_config(redis_config)
        sender = SyncMessageSender()
        return cls(manager, redis, sender)

    @classmethod
    @inlineCallbacks
    def from_config_async(cls, config, amqp_client=None):
        riak_config, redis_config = cls._parse_config(config)
        manager = TxRiakManager.from_config(riak_config)
        redis = yield TxRedisManager.from_config(redis_config)
        sender = None
        if amqp_client is not None:
            sender = AsyncMessageSender(amqp_client)
        returnValue(cls(manager, redis, sender))

    def get_user_api(self, user_account_key):
        return VumiUserApi(self, user_account_key)

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

    def send_command(self, worker_name, command, *args, **kwargs):
        """Create a VumiApiCommand and send it.

        :param str worker_name: Name of worker to send command to.
        :param str command: Type of command to send.
        :param *args: Positional args for command.
        :param **kwargs: Keyword args for command.
        """
        if self.mapi is None:
            raise VumiError("No message sender on API object.")
        return self.mapi.send_command(
            VumiApiCommand.command(worker_name, command, *args, **kwargs))

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

    def batch_outbound_keys(self, batch_id):
        """Return a list of outbound message keys.

        :param str batch_id:
            batch to get outbound message keys for
        :returns:
            list of message keys.
        """
        return self.mdb.batch_outbound_keys(batch_id)

    def batch_inbound_keys(self, batch_id):
        """Return a list of inbound message keys.

        :param str batch_id:
            batch to get inbound message keys for
        :returns:
            list of message keys.
        """
        return self.mdb.batch_inbound_keys(batch_id)

    @Manager.calls_manager
    def batch_tags(self, batch_id):
        """Return a list of tags associated with a given batch.

        :type batch_id: str
        :param batch_id:
            batch to get tags for
        :rtype:
            list of tags
        """
        batch = yield self.mdb.get_batch(batch_id)
        returnValue(list(batch.tags))

    def acquire_tag(self, pool):
        """Acquire a tag from a given tag pool.

        Tags should be held for the duration of a conversation.

        :type pool: str
        :param pool:
            name of the pool to retrieve tags from.
        :rtype:
            The tag acquired or None if no tag was available.
        """
        return self.tpm.acquire_tag(pool)

    def acquire_specific_tag(self, tag):
        """Acquire a specific tag.

        Tags should be held for the duration of a conversation.

        :type tag: tag tuple
        :param tag:
            The tag to acquire.
        :rtype:
            The tag acquired or None if the tag was not available.
        """
        return self.tpm.acquire_specific_tag(tag)

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


class SyncMessageSender(object):
    def __init__(self):
        self.publisher_config = VumiApiCommand.default_routing_config()
        from go.vumitools import api_celery
        self.api_celery = api_celery

    def send_command(self, command):
        self.api_celery.send_command_task.delay(command, self.publisher_config)


class AsyncMessageSender(object):
    def __init__(self, amqp_client):
        self.publisher_config = VumiApiCommand.default_routing_config()
        self.amqp_client = amqp_client
        self.publisher = None

    @inlineCallbacks
    def send_command(self, command):
        if self.publisher is None:
            self.publisher = yield self.amqp_client.start_publisher(
                self.make_publisher())
        self.publisher.publish_message(command)

    def make_publisher(self):
        "Build a Publisher class with the right attributes on it."
        return type("VumiApiCommandPublisher", (Publisher,),
                    self.publisher_config.copy())


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


class VumiApiEvent(Message):

    _DEFAULT_ROUTING_CONFIG = {
        'exchange': 'vumi',
        'exchange_type': 'direct',
        'routing_key': 'vumi.event',
        }

    @classmethod
    def default_routing_config(cls):
        return cls._DEFAULT_ROUTING_CONFIG.copy()

    @classmethod
    def event(cls, account_key, conversation_key, event_type, content):
        return cls(account_key=account_key,
                   conversation_key=conversation_key,
                   event_type=event_type,
                   content=content)
