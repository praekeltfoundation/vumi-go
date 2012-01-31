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

    def batch_start(self):
        """Start a message batch.

        :rtype:
            Returns the batch_id of the new batch.
        """
        return self.mdb.batch_start()

    def batch_send(self, batch_id, msg, addresses):
        """Send a batch of text message to a list of addresses.

        Use multiple calls to :meth:`batch_send` if you have *lots* of
        addresses and don't want to pass them all in one API
        call. Messages passed to multiple calls to :meth:`batch_send`
        do not have to be the same.

        :type batch_id:
        :param batch_id:
            batch to append the messages too
        :type msg: unicode
        :param msg:
            text to send
        :type addresses:
        :param msg:
            list of addresses to send messages to
        :rtype:
            None.
        """
        return self.mapi.batch_send(batch_id, msg, addresses)

    def batch_status(self, batch_id):
        """Check the status of a batch of messages.

        :type batch_id:
        :param batch_id:
            batch to check the status of
        :rtype:
            TODO: define return
        """
        return self.mdb.batch_status()


class MessageStore(object):
    """Vumi Go message store.

    HBase-like data schema:

      # [row_id] -> [family] -> [columns]

      batches:
        batch_id -> messages -> column names are message ids

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
        self.r_server = redis.Redis(**self.r_config)

    def batch_start(self):
        batch_id = uuid4().get_hex()
        self._init_status(batch_id)
        self._put_row('batches', batch_id, 'messages', {})
        return batch_id

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

    def get_inbound_message(self, msg_id):
        body_data = self._get_row('inbound_messages', msg_id, 'body')
        return self._msg_from_body_data(TransportUserMessage, body_data)

    def batch_status(self, batch_id):
        return self._get_status(batch_id)

    def batch_messages(self, batch_id):
        return self._get_row('batches', batch_id, 'messages').keys()

    def message_batches(self, msg_id):
        return self._get_row('messages', msg_id, 'batches').keys()

    def message_events(self, msg_id):
        return self._get_row('messages', msg_id, 'events').keys()

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

    def batch_send(self, batch_id, msg, addresses):
        self.sender_api.batch_send_task.delay(batch_id, msg, addresses,
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
    def send(cls, batch_id, msg, address):
        return cls(**{
            'command': 'send',
            'batch_id': batch_id,
            'content': msg,
            'to_addr': address,
            })
