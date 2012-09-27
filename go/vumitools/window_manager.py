# -*- test-case-name: go.vumitools.tests.test_window_manager -*-
import json
import uuid
import time

from twisted.internet.defer import inlineCallbacks, returnValue


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
        self.redis = redis.sub_manager(self.name)

    def get_windows(self):
        return self.redis.zrange(self.WINDOW_KEY, 0, -1)

    def window_key(self, *keys):
        return ':'.join([self.WINDOW_KEY] + map(str, keys))

    def flight_key(self, *keys):
        return self.window_key(self.FLIGHT_KEY, *keys)

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
        yield self.redis.zadd(self.window_key(window_id), **{
            key: time.time()
            })
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
            next_keys = yield self.redis.zrange(window_key, 0,
                room_available - 1)
            for key in next_keys:
                yield self.redis.zadd(flight_key, **{key: time.time()})
                yield self.redis.zrem(self.window_key(window_id), key)
            returnValue(next_keys)
        else:
            returnValue([])

    def count_waiting(self, window_id):
        window_key = self.window_key(window_id)
        return self.redis.zcard(window_key)

    def count_in_flight(self, window_id):
        flight_key = self.flight_key(window_id)
        return self.redis.zcard(flight_key)

    @inlineCallbacks
    def get(self, window_id, key):
        json_data = yield self.redis.get(self.window_key(window_id, key))
        returnValue(json.loads(json_data))

    @inlineCallbacks
    def remove(self, window_id, key):
        yield self.redis.zrem(self.flight_key(window_id), key)
        yield self.redis.delete(self.window_key(window_id, key))

