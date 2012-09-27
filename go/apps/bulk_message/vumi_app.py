# -*- test-case-name: go.apps.bulk_message.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""
import json
import uuid
import time

from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet import reactor

from vumi.middleware.tagger import TaggingMiddleware
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker


class WindowException(Exception):
    pass

class WindowManager(object):

    WINDOW_KEY = 'windows'
    FLIGHT_KEY = 'inflight'

    def __init__(self, redis, name='window_manager', window_size=100,
        check_interval=2):
        self.name = name
        self.window_size = window_size
        self.check_interval = 2
        self.redis = redis.submanager(self.name)

    def get_windows(self):
        return self.redis.smembers(self.WINDOW_KEY)

    def window_key(self, *keys):
        return ':'.join([self.WINDOW_KEY] + map(str, keys))

    def flight_key(self, *keys):
        return self.window_key(self.FLIGHT_KEY, *keys)

    @inlineCallbacks
    def create(self, window_id):
        if (yield self.redis.sismember(self.WINDOW_KEY, window_id)):
            raise WindowException('Window already exists: %s' % (window_id,))
        yield self.redis.sadd(self.WINDOW_KEY, window_id)

    @inlineCallbacks
    def add(self, window_id, *args, **kwargs):
        key = uuid.uuid4().get_hex()
        yield self.redis.zadd(self.window_key(window_id), key=time.time())
        yield self.redis.set(self.window_key(window_id, key),
            json.dumps([args, kwargs]))

    def next(self, window_id):

        window_key = self.window_key(window_id)
        flight_key = self.flight_key(window_id)

        @inlineCallbacks
        def check(d):
            window_size = yield self.redis.scard(window_key)
            if window_size == 0:
                raise StopIteration()

            flight_size = yield self.redis.scard(flight_key)
            room_available = window_size - flight_size
            if room_available:
                next_keys = self.redis.zrange(window_key, 0, room_available)
                for key in next_keys:
                    yield self.redis.sadd(flight_key, key)
                d.callback(next_keys)
            else:
                reactor.callLater(self.check_interval, check, d)

        next_available = Deferred()
        reactor.callLater(0, self.next, next_available)
        return next_available

    def get(self, window_id, key):
        return self.redis.get(self.window_key(window_id, key))

    @inlineCallbacks
    def remove(self, window_id, key):
        yield self.redis.zrem(self.window_key(window_id), key)
        yield self.redis.delete(self.window_key(window_id, key))

class BulkMessageApplication(GoApplicationWorker):
    """
    Application that accepts 'send message' commands and does exactly that.
    """
    SEND_TO_TAGS = frozenset(['default'])
    worker_name = 'bulk_message_application'
    allowed_ack_window = 100


    @inlineCallbacks
    def setup_application(self):
        yield super(BulkMessageApplication, self).setup_application()
        self.window_manager = WindowManager()

    @inlineCallbacks
    def send_message(self, batch_id, to_addr, content, msg_options):
        msg = yield self.send_to(to_addr, content, **msg_options)
        yield self.vumi_api.mdb.add_outbound_message(msg, batch_id=batch_id)
        log.info('Stored outbound %s' % (msg,))

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):

        if is_client_initiated:
            log.warning('Trying to start a client initiated conversation '
                'on a bulk message send.')
            return

        conv = yield self.get_conversation(batch_id, conversation_key)
        if conv is None:
            log.warning('Cannot find conversation for batch_id: %s '
                'and conversation_key: %s' % (batch_id, conversation_key))
            return

        to_addresses = yield conv.get_opted_in_addresses()
        if extra_params.get('dedupe'):
            to_addresses = set(to_addresses)
        yield self.send_chunk(batch_id, msg_options, conv, to_addresses)

    @inlineCallbacks
    def create_window(self, key, to_addrs, *args, **kwargs):
        for to_addr in to_addrs:
            yield self.ack_window_redis.lpush(key, to_addr)

    @inlineCallbacks
    def send_chunk(self, batch_id, msg_options, conv, to_addresses):
        for to_addr in to_addresses:
            yield self.send_message(batch_id, to_addr,
                                    conv.message, msg_options)

    def consume_user_message(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        return self.vumi_api.mdb.add_inbound_message(msg, tag=tag)

    @inlineCallbacks
    def consume_ack(self, event):
        self.ack_window_redis.rpop()
        return self.vumi_api.mdb.add_event(event)

    def consume_delivery_report(self, event):
        return self.vumi_api.mdb.add_event(event)

    def close_session(self, msg):
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        return self.vumi_api.mdb.add_inbound_message(msg, tag=tag)

    @inlineCallbacks
    def process_command_send_message(self, *args, **kwargs):
        command_data = kwargs['command_data']
        log.info('Processing send_message: %s' % kwargs)
        yield self.send_message(
                command_data['batch_id'],
                command_data['to_addr'],
                command_data['content'],
                command_data['msg_options'])
