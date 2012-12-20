# -*- test-case-name: go.apps.jsbox.tests.test_metrics -*-
# -*- coding: utf-8 -*-

"""Metrics for JS Box sandboxes"""

import time
import json
import math

from twisted.internet.defer import inlineCallbacks, returnValue, maybeDeferred
from twisted.internet.task import LoopingCall

from vumi.application.sandbox import SandboxResource
from vumi.persist.fields import Unicode, ForeignKey, Json
from vumi.persist.model import Model
from vumi import log
from go.vumitools.account import UserAccount, PerAccountStore


class MetricsResource(SandboxResource):
    """Resource that provides metric storing."""

    # default number of seconds between metric updates
    DEFAULT_METRIC_INTERVAL = 300

    def setup_resource(self):
        metric_interval = self.config.get('metric_interval',
                                          self.DEFAULT_METRIC_INTERVAL)
        self.metrics_manager = MetricStoreManager(
            self.app_worker.vumi_api, metric_interval,
            update_callback=self._update_holodeck)

    @inlineCallbacks
    def teardown_resource(self):
        yield self.metrics_manager.stop()

    def _update_holodeck(self, user_account_key, store):
        # TODO: implement
        pass

    def _event_for_command(self, etype, command):
        return MetricEvent(event=etype, store=command.get('store', 'default'),
                           metric=command['metric'],
                           value=float(command['value']))

    @inlineCallbacks
    def _process_event_command(self, etype, user_account_key, command):
        try:
            event = self._event_for_command(etype, command)
        except Exception, e:
            returnValue(self.reply(command, success=False, reason=str(e)))
        yield self.metrics_manager.push_event(user_account_key, event)
        returnValue(self.reply(command, success=True))

    def handle_inc(self, api, command):
        return self._process_event_command(MetricEvent.INC, command)

    def handle_set(self, api, command):
        return self._process_event_command(MetricEvent.SET, command)


class MetricsBundle(Model):
    """A metric store attached to an account"""
    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255, index=True)
    metrics = Json()


class MetricsBundleStore(PerAccountStore):
    def setup_proxies(self):
        self.metrics_bundles = self.manager.proxy(MetricsBundle)


class MetricEvent(object):

    INC, SET = "inc", "set"

    def __init__(self, event, store, metric, value, timestamp=None):
        self.event = event
        self.store = store
        self.metric = metric
        self.value = value
        if timestamp is None:
            timestamp = time.time()
        self.timestamp = timestamp

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return all((self.event == other.event, self.store == other.store,
                    self.metric == other.metric, self.value == other.value,
                    self.timestamp == other.timestamp))

    def to_json(self):
        return json.dumps({'event': self.event, 'store': self.store,
                           'metric': self.metric, 'value': self.value,
                           'timestamp': self.timestamp})

    @classmethod
    def from_json(cls, data):
        return cls(**json.loads(data))


class MetricStoreManager(object):

    looping_call = LoopingCall

    def __init__(self, api, metric_interval, polling_interval=None,
                 update_callback=None):
        self.api = api
        self.redis = api.redis.sub_manager("metrics_store_manager")
        self.metric_interval = metric_interval
        self.polling_interval = (polling_interval
                                 if polling_interval is not None
                                 else metric_interval)
        self.update_callback = update_callback

        self.update_loop = self.looping_call(self.process_updated_stores)
        self.update_loop_done = self.update_loop.start(self.polling_interval)

    @inlineCallbacks
    def stop(self):
        if self.update_loop.running:
            self.update_loop.stop()
            yield self.update_loop_done

    def metrics_bundle_store(self, user_account_key):
        return MetricsBundleStore(self.api.manager, user_account_key)

    def rkey(self, *args):
        return ":".join(args)

    def store_id(self, user_account_key, store):
        return self.rkey(user_account_key, store)

    def parse_store_id(self, store_id):
        user_account_key, store = store_id.split(':')
        return user_account_key, store

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
        return self.redis.zadd(events_key, timestamp, event.to_json())

    @inlineCallbacks
    def pull_events(self, store_id, start, end):
        events_key = self.events_key(store_id)
        start = "(%f" % start
        end = "%f" % end
        raw_events = yield self.redis.zrangebyscore(events_key, start, end)
        returnValue([MetricEvent.from_json(ev) for ev in raw_events])

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
            returnValue(None)
        returnValue(json.loads(events[0]))

    @inlineCallbacks
    def add_event(self, user_account_id, event):
        store_id = self.store_id(user_account_id, event.store)
        yield self.mark_store_updated(store_id)
        yield self.push_event(store_id, event)

    @inlineCallbacks
    def process_updated_stores(self):
        while True:
            store_id = yield self.pop_updated()
            if store_id is None:
                break
            # most recently completed metric interval
            final_timebucket = self.timebucket(time.time() -
                                               self.metric_interval)

            current_timebucket = self.get_set_last_timebucket(store_id,
                                                              final_timebucket)
            if current_timebucket is None:
                # the first time progressing we start from timebucket
                # containing the first unprocessed event
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
        user_account_key, store = self.parse_store_id(store_id)
        metrics_bundle_store = self.metrics_bundle_store(user_account_key)
        metrics_bundles = metrics_bundle_store.metrics_bundles
        bundles = yield metrics_bundles.index_lookup('name', store)
        if not bundles:
            metrics_bundle = metrics_bundles(user_account=user_account_key,
                                             name=store, metrics={})
        elif len(bundles) == 1:
            metrics_bundle = bundles[0]
        else:
            log.error("Found multiple bundles for store id %r" % (store_id,))
            return

        events = yield self.pull_events(store_id, start, end)
        for ev in events:
            self.apply_event(metrics_bundle, ev)

        yield metrics_bundle.save()
        yield self.delete_events(store_id, start, end)
        if self.update_callback is not None:
            yield maybeDeferred(self.update_callback, user_account_key, store)

    def apply_event(self, metrics_bundle, event):
        method_name = 'apply_%s_event' % event['event']
        method = getattr(self, method_name, self.apply_unknown_event)
        return method(metrics_bundle, event)

    def apply_unknown_event(self, mb, ev):
        store_id = self.store_id(mb.user_account_key, mb.name)
        log.warn("Unknown event for store_id %r: %r" % (store_id, ev))

    def apply_inc_event(self, mb, ev):
        mb.metrics[ev.metric] = mb.metrics.get(ev.metric, 0) + ev.value

    def apply_set_event(self, mb, ev):
        mb.metrics[ev.metric] = ev.value
