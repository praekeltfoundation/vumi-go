# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Vumi API for high-volume messaging."""

from uuid import uuid4
import json

from vumi.message import Message, TransportEvent


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

    def __init__(self, config):
        import redis
        self.r_prefix = config.get('store_prefix', 'message_store')
        self.r_config = config.get('redis', {})
        self.r_server = redis.Redis(**self.r_config)

    def _event_column(self, event_name):
        return 'no_%s' % (event_name,)

    def _inc_event_column(self, status, event_name):
        column_name = self._event_column(event_name)
        count = int(status[column_name])
        status[column_name] = str(count + 1)

    def batch_start(self):
        batch_id = uuid4()
        events = TransportEvent.EVENT_TYPES + ['message', 'sent']
        initial_status = dict((self._event_column(event), '0')
                              for event in events)
        self._put_row('batches', batch_id, 'messages', {})
        self._put_row('batches', batch_id, 'status', initial_status)
        return batch_id

    def add_message(self, batch_id, msg):
        msg_id = msg['message_id']
        body_data = dict((k, json.encode(v)) for k, v in msg.payload.items())
        self._put_row('messages', msg_id, 'body', body_data)
        self._put_row('messages', msg_id, 'events', {})

        self._put_row('messages', msg_id, 'batches', {batch_id: '1'})
        self._put_row('batches', batch_id, 'messages', {msg_id: '1'})

        batch_status = self._get_row('batches', batch_id, 'status')
        self._inc_event_column(batch_status, 'message')
        self._inc_event_column(batch_status, 'sent')
        self._put_row('batches', batch_id, 'status', batch_status)

    def add_event(self, event):
        event_id = event['event_id']
        body_data = dict((k, json.encode(v)) for k, v in event.payload.items())
        self._put_row('events', event_id, 'body', body_data)
        msg_id = event['user_message_id']
        self._put_row('messages', msg_id, 'events', {event_id, '1'})

        event_type = event['event_type']
        for batch_id in self._get_row('messages', msg_id, 'batches'):
            batch_status = self._get_row('batches', batch_id, 'status')
            self._inc_event_column(batch_status, event_type)
            self._put_row('batches', batch_id, 'status')

    def batch_status(self, batch_id):
        return self._get_row('batches', batch_id, 'status')

    # [row_id] -> [family] -> [columns]
    #
    # batches:
    # batch_id -> messages -> column names are message ids
    #          -> status -> no_messages, no_sent, no_acks, no_delivered

    # messages:
    # message_id -> body -> column names are message fields,
    #                       values are JSON encoded
    #            -> events -> column names are event ids
    #            -> batches -> column names are batch ids

    # events:
    # event_id -> body -> column names are message fields,
    #                     values are JSON encoded

    # interface to redis -- intentionally made to look
    # like a limited subset of HBase.

    def _get_row(self, table, row_id, family):
        """Retreive a set of column values from storage."""
        r_key = self._row_key(table, row_id, family)
        return self.r_server.hgetall(r_key)

    def _put_row(self, table, row_id, family, data):
        """Update a set of column values in storage."""
        r_key = self._row_key(table, row_id, family)
        self.r_server.hmset(r_key, data)

    def _row_key(self, table, row_id, family):
        """Internal method for use by _get_row and _put_row."""
        return ":".join(self.r_prefix, table, family, row_id)


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
