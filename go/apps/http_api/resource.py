import json
import copy
from datetime import datetime

from functools import partial

from twisted.web import resource, http, util
from twisted.web.server import NOT_DONE_YET
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.guard import BasicCredentialFactory
from twisted.cred import portal
from twisted.internet.error import ConnectionDone
from twisted.internet.defer import (Deferred, DeferredList, inlineCallbacks,
                                    returnValue)

from vumi.message import TransportUserMessage, TransportEvent
from vumi.errors import InvalidMessage
from vumi import log

from go.apps.http_api.auth import ConversationRealm, ConversationAccessChecker


class Stream(resource.Resource):

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.vumi_api = self.worker.vumi_api
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

    def render_PUT(self, request):
        d = Deferred()
        d.addCallback(self.handle_PUT)
        d.callback(request)
        return NOT_DONE_YET

    @inlineCallbacks
    def handle_PUT(self, request):
        data = json.loads(request.content.read())

        user_account = request.getUser()
        user_api = self.vumi_api.get_user_api(user_account)
        conversation = yield user_api.get_wrapped_conversation(
                                self.conversation_key)

        try:
            tum = TransportUserMessage(_process_fields=True, **data)
        except InvalidMessage:
            request.setResponseCode(http.BAD_REQUEST, 'Invalid Message')
            request.finish()
            return

        in_reply_to = tum['in_reply_to']
        if in_reply_to:
            # Using the proxy's load() directly instead of
            # `mdb.get_inbound_message(msg_id)` because that gives us the
            # actual message, not the OutboundMessage. We need the
            # OutboundMessage to get the batch and verify the `user_account`
            msg = yield self.vumi_api.mdb.inbound_messages.load(in_reply_to)
            if msg is None:
                request.setResponseCode(http.BAD_REQUEST,
                                            'Invalid in_reply_to value')
                request.finish()
                return

            batch = yield msg.batch.get()
            if batch is None or (batch.metadata['user_account']
                                                    != user_account):
                request.setResponseCode(http.BAD_REQUEST,
                                        'Invalid in_reply_to value')
                request.finish()
                return

        payload = copy.deepcopy(tum.payload.copy())
        to_addr = payload.pop('to_addr')
        content = payload.pop('content')
        yield self.send_to(conversation, to_addr, content, **payload)
        request.setResponseCode(http.OK)
        request.finish()

    @inlineCallbacks
    def send_to(self, conversation, to_addr, content, **payload):

        # FIXME:    At some point this needs to be done better as it makes some
        #           assumption about how messages are routed which won't be
        #           true for very much longer.
        tag = (conversation.delivery_tag_pool, conversation.delivery_tag)
        msg_options = yield conversation.make_message_options(tag)

        payload.update(msg_options)
        payload.update({
            'transport_name': self.worker.transport_name,
            'timestamp': datetime.utcnow(),
            'message_version': TransportUserMessage.MESSAGE_VERSION,
        })

        msg = TransportUserMessage(to_addr=to_addr, content=content, **payload)
        resp = yield self.worker._publish_message(msg)
        returnValue(resp)


class ConversationResource(resource.Resource):

    CONCURRENCY_LIMIT = 10

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.redis = worker.redis
        self.conversation_key = conversation_key

    def key(self, *args):
        return ':'.join(['concurrency'] + map(unicode, args))

    def is_allowed(self, user_id):
        d = self.redis.get(self.key(user_id))
        d.addCallback(lambda resp: int(resp or 0) < self.CONCURRENCY_LIMIT)
        d.addErrback(log.error)
        return d

    def track_request(self, user_id):
        return self.redis.incr(self.key(user_id))

    def release_request(self, err, user_id):
        return self.redis.decr(self.key(user_id))

    def getChild(self, path, request):
        return util.DeferredResource(self.getDeferredChild(path, request))

    @inlineCallbacks
    def getDeferredChild(self, path, request):

        class_map = {
            'events.json': EventStream,
            'messages.json': MessageStream,
        }
        stream_class = class_map.get(path)

        if stream_class is None:
            returnValue(resource.NoResource())

        user_id = request.getUser()
        if (yield self.is_allowed(user_id)):

            # remove track when request is closed
            finished = request.notifyFinish()
            finished.addBoth(self.release_request, user_id)

            yield self.track_request(user_id)
            returnValue(stream_class(self.worker, self.conversation_key))

        returnValue(resource.ErrorPage(http.FORBIDDEN, 'Forbidden',
                                        'Too many concurrent connections'))


class StreamingResource(resource.Resource):

    def __init__(self, worker):
        resource.Resource.__init__(self)
        self.worker = worker

    def getChild(self, conversation_key, request):
        if conversation_key:

            resource = ConversationResource(self.worker, conversation_key)

            checker = ConversationAccessChecker(self.worker.vumi_api,
                                                conversation_key)
            realm = ConversationRealm(resource)
            p = portal.Portal(realm, [checker])

            factory = BasicCredentialFactory("Conversation Stream")
            protected_resource = HTTPAuthSessionWrapper(p, [factory])

            return protected_resource
