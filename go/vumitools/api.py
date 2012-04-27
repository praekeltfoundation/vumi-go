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
        r_server = get_redis(config)

        # tagpool manager
        tpm_config = config.get('tagpool_manager', {})
        tpm_prefix = tpm_config.get('tagpool_prefix', 'tagpool_store')
        self.tpm = TagpoolManager(r_server, tpm_prefix)
        # message store
        mdb_config = config.get('message_store', {})
        mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        self.manager = RiakManager.from_config({'bucket_prefix': mdb_prefix})
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
