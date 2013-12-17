# -*- test-case-name: go.apps.http_api.tests.test_vumi_app -*-

from functools import partial

from twisted.web.server import NOT_DONE_YET
from twisted.internet.error import ConnectionDone
from twisted.internet.defer import Deferred

from vumi.message import TransportUserMessage, TransportEvent
from vumi import log

from go.apps.http_api_nostream.resource import (
    BaseResource, MessageResource, MetricResource, ConversationResource)


# NOTE: This module subclasses and uses things from go.apps.http_api_nostream.


class StreamResourceMixin(object):

    message_class = None
    proxy_buffering = False
    encoding = 'utf-8'
    content_type = 'application/json; charset=%s' % (encoding,)

    def setup_stream_resource(self, worker, conversation_key):
        self.stream_ready = Deferred()
        self.stream_ready.addCallback(self.setup_stream)
        self._callback = None
        self._rk = self.routing_key % {
            'transport_name': self.worker.transport_name,
            'conversation_key': self.conversation_key,
        }

    def render_GET(self, request):
        resp_headers = request.responseHeaders
        resp_headers.addRawHeader('Content-Type', self.content_type)
        # Turn off proxy buffering, nginx will otherwise buffer our streaming
        # output which makes clients sad.
        # See #proxy_buffering at
        # http://nginx.org/en/docs/http/ngx_http_proxy_module.html
        resp_headers.addRawHeader('X-Accel-Buffering',
                                  'yes' if self.proxy_buffering else 'no')
        # Twisted's Agent has trouble closing a connection when the server has
        # sent the HTTP headers but not the body, but sometimes we need to
        # close a connection when only the headers have been received.
        # Sending an empty string as a workaround gets the body consumer
        # stuff started anyway and then we have the ability to close the
        # connection.
        request.write('')
        done = request.notifyFinish()
        done.addBoth(self.teardown_stream)
        self._callback = partial(self.publish, request)
        self.stream_ready.callback(request)
        return NOT_DONE_YET

    def setup_stream(self, request):
        return self.worker.register_client(self._rk, self.message_class,
                                           self._callback)

    def teardown_stream(self, err):
        if not (err is None or err.trap(ConnectionDone)):
            log.error(err)
        log.info('Unregistering: %s, %s' % (self._rk, err.getErrorMessage()))
        return self.worker.unregister_client(self._rk, self._callback)

    def publish(self, request, message):
        line = u'%s\n' % (message.to_json(),)
        request.write(line.encode(self.encoding))


class EventStream(BaseResource, StreamResourceMixin):

    message_class = TransportEvent
    routing_key = '%(transport_name)s.stream.event.%(conversation_key)s'

    def __init__(self, worker, conversation_key):
        BaseResource.__init__(self, worker, conversation_key)
        self.setup_stream_resource(worker, conversation_key)


class MessageStream(MessageResource, StreamResourceMixin):

    message_class = TransportUserMessage
    routing_key = '%(transport_name)s.stream.message.%(conversation_key)s'

    def __init__(self, worker, conversation_key):
        MessageResource.__init__(self, worker, conversation_key)
        self.setup_stream_resource(worker, conversation_key)


class StreamingConversationResource(ConversationResource):

    def get_child_resource(self, path):
        return {
            'events.json': EventStream,
            'messages.json': MessageStream,
            'metrics.json': MetricResource,
        }.get(path)
