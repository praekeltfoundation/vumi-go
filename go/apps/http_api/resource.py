import json
import copy

from functools import partial

from twisted.web import resource, http, util
from twisted.web.server import NOT_DONE_YET
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.guard import BasicCredentialFactory
from twisted.cred import portal
from twisted.internet.error import ConnectionDone
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

from vumi import errors
from vumi.blinkenlights import metrics
from vumi.message import TransportUserMessage, TransportEvent
from vumi.errors import InvalidMessage
from vumi import log

from go.apps.http_api.auth import ConversationRealm, ConversationAccessChecker


class BaseResource(resource.Resource):

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.conversation_key = conversation_key
        self.vumi_api = self.worker.vumi_api
        self.user_apis = {}

    def get_user_api(self, user_account):
        if user_account in self.user_apis:
            return self.user_apis[user_account]

        user_api = self.vumi_api.get_user_api(user_account)
        self.user_apis[user_account] = user_api
        return user_api

    def get_conversation(self, user_account, conversation_key=None):
        conversation_key = conversation_key or self.conversation_key
        user_api = self.get_user_api(user_account)
        return user_api.get_wrapped_conversation(conversation_key)


class StreamResource(BaseResource):

    message_class = None

    def __init__(self, worker, conversation_key):
        BaseResource.__init__(self, worker, conversation_key)
        self.stream_ready = Deferred()
        self.stream_ready.addCallback(self.setup_stream)
        self._callback = None
        self._rk = self.routing_key % {
            'transport_name': self.worker.transport_name,
            'conversation_key': self.conversation_key,
        }

    def render_GET(self, request):
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
        return self.worker.unregister_client(self._rk, self._callback)

    def publish(self, request, message):
        line = u'%s\n' % (message.to_json(),)
        request.write(line.encode('utf-8'))


class InvalidAggregate(errors.VumiError):
    pass


class EventStream(StreamResource):

    message_class = TransportEvent
    routing_key = '%(transport_name)s.stream.event.%(conversation_key)s'


class MessageStream(StreamResource):

    message_class = TransportUserMessage
    routing_key = '%(transport_name)s.stream.message.%(conversation_key)s'

    def render_PUT(self, request):
        d = Deferred()
        d.addCallback(self.handle_PUT)
        d.callback(request)
        return NOT_DONE_YET

    def get_msg_options(self, payload, white_list=[]):
        raw_payload = copy.deepcopy(payload.copy())
        msg_options = dict((key, value)
                           for key, value in raw_payload.items()
                           if key in white_list)
        return msg_options

    def get_conversation_tag(self, conversation):
        return (conversation.delivery_tag_pool, conversation.delivery_tag)

    @inlineCallbacks
    def handle_PUT(self, request):
        try:
            payload = json.loads(request.content.read())
        except ValueError:
            request.setResponseCode(http.BAD_REQUEST, 'Invalid Message')
            request.finish()
            return

        in_reply_to = payload.get('in_reply_to')
        if in_reply_to:
            yield self.handle_PUT_in_reply_to(request, payload, in_reply_to)
        else:
            yield self.handle_PUT_send_to(request, payload)

    @inlineCallbacks
    def handle_PUT_in_reply_to(self, request, payload, in_reply_to):
        user_account = request.getUser()
        user_api = yield self.get_user_api(user_account)
        conversation = yield self.get_conversation(user_account)

        # Using the proxy's load() directly instead of
        # `mdb.get_inbound_message(msg_id)` because that gives us the
        # actual message, not the OutboundMessage. We need the
        # OutboundMessage to get the batch and verify the `user_account`
        reply_to = yield self.vumi_api.mdb.inbound_messages.load(in_reply_to)
        if reply_to is None:
            request.setResponseCode(http.BAD_REQUEST)
            request.write('Invalid in_reply_to value')
            request.finish()
            return

        batch = yield reply_to.batch.get()
        if batch is None or (batch.metadata['user_account']
                             != user_account):
            request.setResponseCode(http.BAD_REQUEST)
            request.write('Invalid in_reply_to value')
            request.finish()
            return

        msg_options = self.get_msg_options(payload,
                                           ['session_event', 'content'])

        # FIXME:    At some point this needs to be done better as it makes some
        #           assumption about how messages are routed which won't be
        #           true for very much longer.
        tag = self.get_conversation_tag(conversation)
        msg_options.update((yield user_api.msg_options(tag)))

        content = msg_options.pop('content')
        continue_session = (msg_options.pop('session_event', None)
                            != TransportUserMessage.SESSION_CLOSE)
        helper_metadata = msg_options.pop('helper_metadata')
        transport_type = msg_options.pop('transport_type')
        # We need to pop this out of the msg_options, should it exist
        # because otherwise `msg.reply(...)` is unhappy
        msg_options.pop('transport_name', None)
        from_addr = msg_options.pop('from_addr')

        # NOTE:
        #
        # Not able to use `worker.reply_to()` because TransportUserMessage's
        # reply() method sets the `helper_metadata` which it isn't really
        # supposed to do. Because of this we're doing the manual call
        # to `worker._publish_message()` instead.
        msg = reply_to.msg.reply(content, continue_session, **msg_options)

        # These need to be set manually to ensure that stuff cannot be forged.
        msg['helper_metadata'].update(helper_metadata)
        msg['from_addr'] = from_addr
        msg['transport_type'] = transport_type
        msg['transport_name'] = self.worker.transport_name

        yield self.worker._publish_message(msg)

        request.setResponseCode(http.OK)
        request.write(msg.to_json())
        request.finish()

    @inlineCallbacks
    def handle_PUT_send_to(self, request, payload):
        user_account = request.getUser()
        user_api = yield self.get_user_api(user_account)
        conversation = yield self.get_conversation(user_account)

        msg_options = self.get_msg_options(payload, ['content', 'to_addr'])
        tag = self.get_conversation_tag(conversation)
        msg_options.update((yield user_api.msg_options(tag)))
        to_addr = msg_options.pop('to_addr')
        content = msg_options.pop('content')

        msg = yield self.worker.send_to(to_addr, content, **msg_options)

        request.setResponseCode(http.OK)
        request.write(msg.to_json())
        request.finish()


class MetricResource(BaseResource):

    DEFAULT_STORE_NAME = 'default'

    def render_PUT(self, request):
        d = Deferred()
        d.addCallback(self.handle_PUT)
        d.callback(request)
        return NOT_DONE_YET

    def find_aggregate(self, name):
        agg_class = getattr(metrics, name, None)
        if agg_class is None:
            raise InvalidAggregate('%s is not a valid aggregate.' % (name,))
        return agg_class

    def parse_metrics(self, data):
        metrics = []
        for name, value, aggregate in data:
            value = float(value)
            agg_class = self.find_aggregate(aggregate)
            metrics.append((name, value, agg_class))
        return metrics

    @inlineCallbacks
    def handle_PUT(self, request):
        data = json.loads(request.content.read())
        user_account = request.getUser()

        try:
            metrics = self.parse_metrics(data)
        except (ValueError, InvalidAggregate, InvalidMessage):
            request.setResponseCode(http.BAD_REQUEST, 'Invalid Message')
            request.finish()
            return

        conversation = yield self.get_conversation(user_account)
        metadata = conversation.get_metadata(default={})
        http_api_metadata = metadata.get('http_api', {})
        store = http_api_metadata.get('metrics_store', self.DEFAULT_STORE_NAME)
        for name, value, agg_class in metrics:
            self.worker.publish_account_metric(user_account, store, name,
                                                value, agg_class)

        request.finish()


class ConversationResource(resource.Resource):

    CONCURRENCY_LIMIT = 10

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.redis = worker.redis
        self.conversation_key = conversation_key

    def key(self, *args):
        return ':'.join(['concurrency'] + map(unicode, args))

    @inlineCallbacks
    def is_allowed(self, user_id):
        count = int((yield self.redis.get(self.key(user_id))) or 0)
        returnValue(count < self.CONCURRENCY_LIMIT)

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
            'metrics.json': MetricResource,
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
