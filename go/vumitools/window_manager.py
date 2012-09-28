# -*- test-case-name: go.vumitools.tests.test_window_manager -*-
import json
import uuid
import time

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall


class WindowException(Exception):
    pass

class WindowManager(object):

    WINDOW_KEY = 'windows'
    FLIGHT_KEY = 'inflight'
    FLIGHT_STATS_KEY = 'flightstats'

    def __init__(self, redis, name='window_manager', window_size=100,
        flight_lifetime=10, max_flight_retries=10):
        self.name = name
        self.window_size = window_size
        self.flight_lifetime = 10
        self.max_flight_retries = max_flight_retries
        self.redis = redis.sub_manager(self.name)
        self.gc = LoopingCall(self.clear_or_retry_flight_keys)

    def get_windows(self):
        return self.redis.zrange(self.window_key(), 0, -1)

    def window_key(self, *keys):
        return ':'.join([self.WINDOW_KEY] + map(str, keys))

    def flight_key(self, *keys):
        return self.window_key(self.FLIGHT_KEY, *keys)

    def stats_key(self, *keys):
        return self.window_key(self.FLIGHT_STATS_KEY, *keys)

    @inlineCallbacks
    def create(self, window_id):
        if (yield self.redis.zscore(self.WINDOW_KEY, window_id)):
            raise WindowException('Window already exists: %s' % (window_id,))
        yield self.redis.zadd(self.WINDOW_KEY, **{window_id: time.time()})

    @inlineCallbacks
    def remove_window(self, window_id):
        waiting_list = yield self.count_waiting(window_id)
        if waiting_list:
            raise WindowException('Window not empty')
        yield self.redis.zrem(self.WINDOW_KEY, window_id)

    @inlineCallbacks
    def add(self, window_id, data):
        key = uuid.uuid4().get_hex()
        yield self.redis.lpush(self.window_key(window_id), key)
        yield self.redis.set(self.window_key(window_id, key),
            json.dumps(data))

    @inlineCallbacks
    def next(self, window_id):

        window_key = self.window_key(window_id)
        flight_key = self.flight_key(window_id)

        waiting_list = yield self.count_waiting(window_id)
        if waiting_list == 0:
            return

        flight_size = yield self.count_in_flight(window_id)
        room_available = self.window_size - flight_size

        if room_available:
            next_key = yield self.redis.rpoplpush(window_key, flight_key)
            yield self.set_timestamp(window_id, flight_key)
            yield self.increment_tries(window_id, flight_key)
            returnValue(next_key)
        else:
            returnValue(None)

    def set_timestamp(self, window_id, flight_key):
        return self.redis.zadd(self.stats_key(window_id), **{
                flight_key: time.time()
        })

    def increment_tries(self, window_id, flight_key):
        return self.redis.incr(self.stats_key(window_id, flight_key))

    def count_waiting(self, window_id):
        window_key = self.window_key(window_id)
        return self.redis.llen(window_key)

    def count_in_flight(self, window_id):
        flight_key = self.flight_key(window_id)
        return self.redis.llen(flight_key)

    @inlineCallbacks
    def clear_or_retry_flight_keys(self):
        windows = yield self.get_windows()
        for window_id in windows:
            expired_keys = yield self.redis.zcardbyscore(
                self.stats_key(window_id), '-inf',
                time.time() - self.flight_lifetime)
            for key in expired_keys:
                tries = yield self.increment_tries(window_id, key)
                window_key = self.window_key(window_id)
                flight_key = self.flight_key(window_id)
                if tries < self.max_flight_retries:
                    yield self.redis.rpoplpush(flight_key, window_key)
                else:
                    yield self.redis.remove(window_id, key)

    @inlineCallbacks
    def get(self, window_id, key):
        json_data = yield self.redis.get(self.window_key(window_id, key))
        returnValue(json.loads(json_data))

    @inlineCallbacks
    def remove(self, window_id, key):
        yield self.redis.lrem(self.flight_key(window_id), key, 1)
        yield self.redis.delete(self.window_key(window_id, key))
