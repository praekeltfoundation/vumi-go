# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Vumi API for high-volume messaging."""

from uuid import uuid4
from datetime import datetime

from vumi.message import (Message, TransportEvent,
                          TransportUserMessage, from_json, to_json,
                          VUMI_DATE_FORMAT)


class VumiApi(object):

    def __init__(self, config):
        # message store
        self.mdb = MessageStore(config['message_store'])
        # message sending API
        self.mapi = MessageSender(config['message_sender'])

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
        return self.mapi.batch_send(batch_id, msg, msg_options, addresses)

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
        msg_ids = self.mdb.batch_messages(batch_id)
        return [self.mdb.get_message(m_id) for m_id in msg_ids]

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
        reply_ids = self.mdb.batch_replies(batch_id)
        return [self.mdb.get_inbound_message(r_id) for r_id in reply_ids]

    def acquire_tag(self, pool):
        """Acquire a tag from a given tag pool.

        Tags should be held for the duration of a conversation.

        :type pool: str
        :param pool:
            name of the pool to retrieve tags from.
        :rtype:
            str containing the tag
        """
        return self.mdb.acquire_tag(pool)

    def release_tag(self, pool, tag):
        """Release a tag back to the pool it came from.

        Tags should be released only once a conversation is finished.

        :type pool: str
        :param pool:
            name of the pool to return the tag too (must be the same as
            the name of the pool the tag came from).
        :rtype:
            None.
        """
        return self.mdb.release_tag(pool, tag)

    def declare_tags(self, pool, tags):
        """Populate a pool with tags.

        Tags already in the pool are not duplicated.

        :type pool: str
        :param pool:
            name of the pool to add the tags too
        :type tags: list of str
        :param tags:
            list of tags to add to the pool.
        :rtype:
            None
        """
        return self.mdb.declare_tags(pool, tags)


class MessageStore(object):
    """Vumi Go message store.

    HBase-like data schema:

      # [row_id] -> [family] -> [columns]

      batches:
        batch_id -> common -> ['tag']
                 -> messages -> column names are message ids
                 -> replies -> column names are inbound_message ids

      tags:
        tag -> common -> ['current_batch_id']

      messages:
        message_id -> body -> column names are message fields,
                              values are JSON encoded
                   -> events -> column names are event ids
                   -> batches -> column names are batch ids

      inbound_messages:
        message_id -> body -> column names are message fields,
                              values are JSON encoded

      events:
        event_id -> body -> column names are message fields,
                            values are JSON encoded


    Possible future schema tweaks for later:

    * third_party_ids table that maps third party message ids
      to vumi message ids (third_pary:third_party_id -> data
      -> message_id)
    * Consider making message_id "batch_id:current_message_id"
      (this makes retrieving batches of messages fast, it
       might be better to have "timestamp:current_message_id").
    """

    def __init__(self, config):
        import redis
        self.r_prefix = config.get('store_prefix', 'message_store')
        self.r_config = config.get('redis', {})
        redis_cls = config.get('redis_cls', redis.Redis)  # testing hook
        self.r_server = redis_cls(**self.r_config)

    def batch_start(self, tags):
        batch_id = uuid4().get_hex()
        fields = {'tags': to_json(tags)}
        tag_fields = {'current_batch_id': batch_id}
        self._init_status(batch_id)
        self._put_row('batches', batch_id, 'common', fields)
        self._put_row('batches', batch_id, 'messages', {})
        for tag in tags:
            self._put_row('tags', tag, 'common', tag_fields)
        return batch_id

    def acquire_tag(self, pool):
        return self._acquire_tag(pool)

    def release_tag(self, pool, tag):
        return self._release_tag(pool, tag)

    def declare_tags(self, pool, tags):
        return self._declare_tags(pool, tags)

    def _msg_to_body_data(self, msg):
        return dict((k.encode('utf-8'), to_json(v)) for k, v
                     in msg.payload.items())

    def _msg_from_body_data(self, cls, body_data):
        body = dict((k.decode('utf-8'), from_json(v))
                    for k, v in body_data.items())
        # TODO: this is a hack needed because from_json(to_json(x)) != x
        #       if x is a datetime. Remove this once from_json and to_json
        #       are fixed.
        body['timestamp'] = datetime.strptime(body['timestamp'],
                                              VUMI_DATE_FORMAT)
        return cls(**body)

    def _map_inbound_msg_to_tag(self, msg):
        # TODO: this eventually needs to become more generic to support
        #       additional transports
        transport_type = msg['transport_type']
        if transport_type == 'sms':
            tag = "default%s" % (msg['to_addr'][-5:],)
        elif transport_type == 'xmpp':
            tag = msg['to_addr']
        else:
            tag = None
        return tag

    def add_message(self, batch_id, msg):
        msg_id = msg['message_id']
        self._put_row('messages', msg_id, 'body', self._msg_to_body_data(msg))
        self._put_row('messages', msg_id, 'events', {})

        self._put_row('messages', msg_id, 'batches', {batch_id: '1'})
        self._put_row('batches', batch_id, 'messages', {msg_id: '1'})

        self._inc_status(batch_id, 'message')
        self._inc_status(batch_id, 'sent')

    def get_message(self, msg_id):
        body_data = self._get_row('messages', msg_id, 'body')
        return self._msg_from_body_data(TransportUserMessage, body_data)

    def add_event(self, event):
        event_id = event['event_id']
        self._put_row('events', event_id, 'body',
                      self._msg_to_body_data(event))
        msg_id = event['user_message_id']
        self._put_row('messages', msg_id, 'events', {event_id: '1'})

        event_type = event['event_type']
        for batch_id in self._get_row('messages', msg_id, 'batches'):
            self._inc_status(batch_id, event_type)

    def get_event(self, event_id):
        body_data = self._get_row('events', event_id, 'body')
        return self._msg_from_body_data(TransportEvent, body_data)

    def add_inbound_message(self, msg):
        msg_id = msg['message_id']
        self._put_row('inbound_messages', msg_id, 'body',
                      self._msg_to_body_data(msg))
        tag = self._map_inbound_msg_to_tag(msg)
        batch_id = (self.tag_common(tag).get('current_batch_id')
                    if tag else None)
        if batch_id is not None:
            self._put_row('batches', batch_id, 'replies', {msg_id: '1'})

    def get_inbound_message(self, msg_id):
        body_data = self._get_row('inbound_messages', msg_id, 'body')
        return self._msg_from_body_data(TransportUserMessage, body_data)

    def batch_common(self, batch_id):
        common = self._get_row('batches', batch_id, 'common')
        for field in ('tags',):
            common[field] = from_json(common[field])
        return common

    def batch_status(self, batch_id):
        return self._get_status(batch_id)

    def batch_messages(self, batch_id):
        return self._get_row('batches', batch_id, 'messages').keys()

    def batch_replies(self, batch_id):
        return self._get_row('batches', batch_id, 'replies').keys()

    def message_batches(self, msg_id):
        return self._get_row('messages', msg_id, 'batches').keys()

    def message_events(self, msg_id):
        return self._get_row('messages', msg_id, 'events').keys()

    def tag_common(self, tag):
        return self._get_row('tags', tag, 'common')

    # tag pool is stored in Redis since HBase doesn't have a nice
    # list implementation

    def _tag_pool_keys(self, pool):
        return tuple(":".join([self.r_prefix, "tagpools", pool, state])
                     for state in ("free:list", "free:set", "inuse:set"))

    def _acquire_tag(self, pool):
        free_list_key, free_set_key, inuse_set_key = self._tag_pool_keys(pool)
        tag = self.r_server.lpop(free_list_key)
        if tag is not None:
            self.r_server.smove(free_set_key, inuse_set_key, tag)
        return tag

    def _release_tag(self, pool, tag):
        free_list_key, free_set_key, inuse_set_key = self._tag_pool_keys(pool)
        count = self.r_server.smove(inuse_set_key, free_set_key, tag)
        if count == 1:
            self.r_server.rpush(free_list_key, tag)

    def _declare_tags(self, pool, tags):
        free_list_key, free_set_key, inuse_set_key = self._tag_pool_keys(pool)
        new_tags = set(tags)
        old_tags = set(self.r_server.sunion(free_set_key, inuse_set_key))
        for tag in sorted(new_tags - old_tags):
            self.r_server.sadd(free_set_key, tag)
            self.r_server.rpush(free_list_key, tag)

    # batch status is stored in Redis as a cache of batch progress

    def _batch_key(self, batch_id):
        return ":".join([self.r_prefix, "batches", "status", batch_id])

    def _init_status(self, batch_id):
        batch_key = self._batch_key(batch_id)
        events = TransportEvent.EVENT_TYPES.keys() + ['message', 'sent']
        initial_status = dict((event, '0') for event in events)
        self.r_server.hmset(batch_key, initial_status)

    def _inc_status(self, batch_id, event):
        batch_key = self._batch_key(batch_id)
        self.r_server.hincrby(batch_key, event, 1)

    def _get_status(self, batch_id):
        batch_key = self._batch_key(batch_id)
        raw_statuses = self.r_server.hgetall(batch_key)
        statuses = dict((k, int(v)) for k, v in raw_statuses.items())
        return statuses

    # interface to redis -- intentionally made to look
    # like a limited subset of HBase.

    def _get_row(self, table, row_id, family):
        """Retreive a set of column values from storage."""
        r_key = self._row_key(table, row_id, family)
        return self.r_server.hgetall(r_key)

    def _put_row(self, table, row_id, family, data):
        """Update a set of column values in storage."""
        r_key = self._row_key(table, row_id, family)
        if data:
            self.r_server.hmset(r_key, data)

    def _row_key(self, table, row_id, family):
        """Internal method for use by _get_row and _put_row."""
        return ":".join([self.r_prefix, table, family, row_id])


class MessageSender(object):
    def __init__(self, config):
        from go.vumitools import api_celery
        self.config = config
        self.sender_api = api_celery
        self.publisher_config = VumiApiCommand.default_routing_config()

    def batch_send(self, batch_id, msg, msg_options, addresses):
        self.sender_api.batch_send_task.delay(batch_id, msg,
                                              msg_options, addresses,
                                              self.publisher_config)


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
    def send(cls, batch_id, msg, msg_options, address):
        return cls(**{
            'command': 'send',
            'batch_id': batch_id,
            'msg_options': msg_options,
            'content': msg,
            'to_addr': address,
            })
