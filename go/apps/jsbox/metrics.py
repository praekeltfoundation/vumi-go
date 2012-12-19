# -*- test-case-name: go.apps.jsbox.tests.test_metrics -*-
# -*- coding: utf-8 -*-

"""Metrics for JS Box sandboxes"""

import time
import json
import math

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.sandbox import SandboxResource


class MetricsResource(SandboxResource):
    """Resource that provides metric storing."""

    def setup_resource(self):
        self.metrics_store = MetricsStore()

    def teardown_resource(self):
        pass

    def _event_for_command(self, etype, command):
        return {
            'event': etype,
            'metric': command['metric'],
            'value': float(command['value']),
            'timestamp': time.time(),
        }

    @inlineCallbacks
    def _process_event_command(self, etype, store_id, command):
        try:
            event = self._event_for_command(etype, command)
        except Exception, e:
            returnValue(self.reply(command, success=False, reason=str(e)))
        yield self.metric_store.push_event(store_id, event)
        returnValue(self.reply(command, success=True))

    def handle_inc(self, api, command):
        return self._process_event_command("inc", command)

    def handle_set(self, api, command):
        return self._process_event_command("set", command)


class MetricsStore(object):

    def __init__(self, manager, redis, metric_interval, polling_interval=None):
        self.manager = manager
        self.redis = redis
        self.metric_interval = metric_interval
        self.polling_interval = (polling_interval
                                 if polling_interval is not None
                                 else metric_interval)

    def rkey(self, *args):
        return ":".join(args)

    def events_key(self, store_id):
        return self.rkey("stores", store_id, "events")

    def last_timebucket_key(self, store_id):
        return self.rkey("stores", store_id, "last_timebucket")

    def store_updated(self, store_id):
        return self.redis.sadd("updated_stores", store_id)

    def pop_updated(self):
        return self.redis.spop("updated_stores")

    def get_set_last_timebucket(self, store_id, new_timebucket):
        last_timebucket_key = self.last_timebucket_key(store_id)
        return self.redis.getset(last_timebucket_key, new_timebucket)

    def timebucket(self, timestamp):
        intervals = math.floor(timestamp / self.metric_interval)
        return intervals * self.metric_interval

    def push_event(self, store_id, event):
        events_key = self.events_key(store_id)
        timestamp = event['timestamp']
        return self.redis.zadd(events_key, timestamp, json.dumps(event))

    @inlineCallbacks
    def pull_events(self, store_id, start, end):
        events_key = self.events_key(store_id)
        start = "(%f" % start
        end = "%f" % end
        raw_events = yield self.redis.zrangebyscore(events_key, start, end)
        returnValue([json.loads(ev) for ev in raw_events])

    def delete_events(self, store_id, start, end):
        events_key = self.events_key(store_id)
        start = "(%f" % start
        end = "%f" % end
        return self.redis.zremrangebyscore(events_key, start, end)

    @inlineCallbacks
    def first_event(self, store_id):
        events_key = self.events_key(store_id)
        events = yield self.redis.zrange(events_key, 0, 1)
        if not events:
            return None
        return json.loads(events[0])

    @inlineCallbacks
    def add_event(self, store_id, event):
        yield self.mark_store_updated(store_id)
        yield self.push_event(store_id, event)

    @inlineCallbacks
    def process_updated_stores(self):
        while True:
            store_id = yield self.pop_updated_store()
            if store_id is None:
                break
            # most recently completed metric interval
            final_timebucket = self.timebucket(time.time() -
                                                 self.metric_interval)

            current_timebucket = self.get_set_last_timebucket(store_id,
                                                              final_timebucket)
            if current_timebucket is None:
                # first time progressing -- start from timebucket containing
                # first unprocessed event
                first_event = yield self.first_event(store_id)
                if first_event is None:
                    continue
                current_timebucket = self.timebucket(first_event['timestamp'])

            while (current_timebucket <
                   final_timebucket + 0.5 * self.metric_interval):
                next_timebucket = current_timebucket + self.metric_interval
                yield self.update_store(store_id, current_timebucket,
                                        next_timebucket)
                current_timebucket = next_timebucket

    @inlineCallbacks
    def update_store(self, store_id, start, end):
        events = yield self.pull_events(store_id, start, end)
        # TODO: load metrics from riak
        for ev in events:
            # TODO: update metrics
            pass
        # TODO: save metrics to riak
        yield self.delete_events(store_id, start, end)
        # TODO: notify holodeck
