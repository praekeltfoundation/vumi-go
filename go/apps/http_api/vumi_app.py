# -*- test-case-name: go.apps.http_api.tests.test_vumi_app -*-
from functools import partial

from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet.error import ConnectionDone
from twisted.internet.defer import (Deferred, DeferredList, inlineCallbacks,
                                    returnValue)

from vumi.message import TransportUserMessage, TransportEvent
from vumi.transports.httprpc import httprpc
from vumi import log

from go.vumitools.api import VumiApi
from go.vumitools.app_worker import GoApplicationWorker


class Stream(resource.Resource):

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.conversation_key = conversation_key
        self.stream_ready = Deferred()
        self.stream_ready.addCallback(self.start_publishing)
        self._consumers = []

    def render_GET(self, request):
        done = request.notifyFinish()
        done.addBoth(self.teardown_stream)
        self.stream_ready.callback(request)
        return NOT_DONE_YET

    @inlineCallbacks
    def setup_stream(self, request):
        self._consumers.extend((yield self.setup_consumers(request)))

    @inlineCallbacks
    def setup_consumers(self, request):
        rk = self.routing_key % {
            'transport_name': self.worker.transport_name,
            'conversation_key': self.conversation_key,
            }
        consumer = yield self.worker.consume(rk,
                            partial(self.publish, request),
                            message_class=self.message_class, paused=True)
        returnValue([consumer])

    def teardown_stream(self, err):
        if not (err is None or err.trap(ConnectionDone)):
            log.error(err)
        return DeferredList([cons.stop() for cons in self._consumers])

    @inlineCallbacks
    def start_publishing(self, request):
        yield self.setup_stream(request)
        for consumer in self._consumers:
            yield consumer.unpause()

    def publish(self, request, message):
        line = u'%s\n' % (message.to_json(),)
        request.write(line.encode('utf-8'))


class EventStream(Stream):

    message_class = TransportEvent
    routing_key = '%(transport_name)s.stream.event.%(conversation_key)s'


class MessageStream(Stream):

    message_class = TransportUserMessage
    routing_key = '%(transport_name)s.stream.message.%(conversation_key)s'


class ConversationResource(resource.Resource):
    """
    Streams messages as they arrive on a consumer.
    """
    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.conversation_key = conversation_key

    def getChild(self, path, request):
        class_map = {
            'events.js': EventStream,
            'messages.js': MessageStream,
        }
        stream_class = class_map.get(path, lambda *a: resource.NoResource())
        return stream_class(self.worker, self.conversation_key)


class StreamingResource(resource.Resource):

    def __init__(self, worker):
        resource.Resource.__init__(self)
        self.worker = worker

    def getChild(self, conversation_key, request):
        if conversation_key:
            return ConversationResource(self.worker, conversation_key)


class StreamingHTTPWorker(GoApplicationWorker):
    """

    :param str web_path:
        The path the HTTP worker should expose the API on
    :param int web_port:
        The port the HTTP worker should open for the API
    :param str health_path:
        The path the resource should receive health checks on.
        Defaults to '/health/'
    """

    def validate_config(self):
        super(StreamingHTTPWorker, self).validate_config()
        self.web_path = self.config['web_path']
        self.web_port = int(self.config['web_port'])
        self.health_path = self.config.get('health_path', '/health/')

    @inlineCallbacks
    def setup_application(self):
        yield super(StreamingHTTPWorker, self).setup_application()
        # Set these to empty dictionaries because we're not interested
        # in using any of the helper functions at this point.
        self._event_handlers = {}
        self._session_handlers = {}
        self.vumi_api = yield VumiApi.from_config_async(self.config)
        # We do give the publisher a key but won't actually use it
        self.stream_publisher = yield self.publish_to(
            '%s.stream.lost_and_found' % (self.transport_name,))

        self.webserver = self.start_web_resources([
            (StreamingResource(self), self.web_path),
            (httprpc.HttpRpcHealthResource(self), self.health_path),
            ], self.web_port)

    def stream(self, stream_class, conversation_key, message):
        # Publish the message by manually specifying the routing key
        return self.stream_publisher.publish(message,
            routing_key=stream_class.routing_key % {
            'transport_name': self.transport_name,
            'conversation_key': conversation_key,
            })

    @inlineCallbacks
    def consume_user_message(self, message):
        md = self.get_go_metadata(message)
        conv_key, conv_type = yield md.get_conversation_info()
        yield self.stream(MessageStream, conv_key, message)

    @inlineCallbacks
    def consume_unknown_event(self, event):
        """
        FIXME:  We're forced to do too much hoopla when trying to link events
                back to the conversation the original message was part of.
        """
        outbound_message = yield self.find_message_for_event(event)
        batch = yield outbound_message.batch.get()
        account_key = batch.metadata['account_key']
        user_api = self.get_user_api(account_key)
        conversations = user_api.conversation_store.conversations
        mr = conversations.index_lookup('batches', batch.key)
        [conv_key] = yield mr.get_keys()
        yield self.stream(EventStream, conv_key, event)

    @inlineCallbacks
    def teardown_application(self):
        yield super(StreamingHTTPWorker, self).teardown_application()
        self.webserver.loseConnection()
