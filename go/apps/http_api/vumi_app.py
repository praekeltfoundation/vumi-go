# -*- test-case-name: go.apps.http_api.tests.test_vumi_app -*-
from collections import defaultdict
import random

from twisted.internet.defer import inlineCallbacks, maybeDeferred

from go.apps.http_api_nostream.auth import AuthorizedResource
from go.apps.http_api_nostream.vumi_app import NoStreamingHTTPWorker
from go.apps.http_api.resource import (
    MessageStream, EventStream, StreamingConversationResource)


# NOTE: This module subclasses and uses things from go.apps.http_api_nostream.


class StreamingClientManager(object):

    MAX_BACKLOG_SIZE = 100
    CLIENT_PREFIX = 'clients'

    def __init__(self, redis):
        self.redis = redis
        self.clients = defaultdict(list)

    def client_key(self, *args):
        return u':'.join([self.CLIENT_PREFIX] + map(unicode, args))

    def backlog_key(self, key):
        return self.client_key('backlog', key)

    @inlineCallbacks
    def flush_backlog(self, key, message_class, callback):
        backlog_key = self.backlog_key(key)
        while True:
            obj = yield self.redis.rpop(backlog_key)
            if obj is None:
                break
            yield maybeDeferred(callback, message_class.from_json(obj))

    def start(self, key, message_class, callback):
        self.clients[key].append(callback)

    def stop(self, key, callback):
        self.clients[key].remove(callback)

    def publish(self, key, msg):
        callbacks = self.clients[key]
        if callbacks:
            callback = random.choice(callbacks)
            return maybeDeferred(callback, msg)
        else:
            return self.queue_in_backlog(key, msg)

    @inlineCallbacks
    def queue_in_backlog(self, key, msg):
        backlog_key = self.backlog_key(key)
        yield self.redis.lpush(backlog_key, msg.to_json())
        yield self.redis.ltrim(backlog_key, 0, self.MAX_BACKLOG_SIZE - 1)


class StreamingHTTPWorker(NoStreamingHTTPWorker):

    worker_name = 'http_api_worker'

    @inlineCallbacks
    def setup_application(self):
        yield super(StreamingHTTPWorker, self).setup_application()

        self.client_manager = StreamingClientManager(
            self.redis.sub_manager('http_api:message_cache'))

    def get_conversation_resource(self):
        return AuthorizedResource(self, StreamingConversationResource)

    def get_all_api_config(self, conversation):
        return conversation.config.get('http_api', {})

    def stream(self, stream_class, conversation_key, message):
        # Publish the message by manually specifying the routing key
        rk = stream_class.routing_key % {
            'transport_name': self.transport_name,
            'conversation_key': conversation_key,
        }
        return self.client_manager.publish(rk, message)

    def register_client(self, key, message_class, callback):
        self.client_manager.start(key, message_class, callback)
        return self.client_manager.flush_backlog(key, message_class, callback)

    def unregister_client(self, conversation_key, callback):
        self.client_manager.stop(conversation_key, callback)

    def send_message_to_client(self, message, conversation, push_url):
        if push_url:
            return self.push(conversation.user_account.key, push_url, message)
        else:
            return self.stream(MessageStream, conversation.key, message)

    def send_event_to_client(self, event, conversation, push_url):
        if push_url:
            return self.push(conversation.user_account.key, push_url, event)
        else:
            return self.stream(EventStream, conversation.key, event)

    def get_health_response(self):
        return str(sum([len(callbacks) for callbacks in
                   self.client_manager.clients.values()]))
