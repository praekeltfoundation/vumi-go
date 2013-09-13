# -*- test-case-name: go.apps.http_api.tests.test_vumi_app -*-

import json
import copy

from functools import partial

from twisted.web import resource, http, util
from twisted.web.server import NOT_DONE_YET
from twisted.web.guard import HTTPAuthSessionWrapper, BasicCredentialFactory
from twisted.cred import portal
from twisted.internet.error import ConnectionDone
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

from vumi import errors
from vumi.blinkenlights import metrics
from vumi.message import TransportUserMessage, TransportEvent
from vumi.errors import InvalidMessage
from vumi.config import ConfigContext
from vumi import log

from go.apps.http_api.auth import ConversationRealm, ConversationAccessChecker
from go.vumitools.utils import MessageMetadataHelper


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
    proxy_buffering = False
    encoding = 'utf-8'
    content_type = 'application/json; charset=%s' % (encoding,)

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

    def get_load_balancer_metadata(self, payload):
        """
        Probe for load_balancer config in the helper metadata
        and return it.

        TODO: Replace with a more generic mechanism for filtering
        helper_metadata. See Go issue #659.
        """
        helper_metadata = payload.get('helper_metadata', {})
        load_balancer = helper_metadata.get('load_balancer')
        if load_balancer is not None:
            return {'load_balancer': copy.deepcopy(load_balancer)}
        return {}

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
        conversation = yield self.get_conversation(user_account)

        reply_to = yield self.vumi_api.mdb.get_inbound_message(in_reply_to)
        if reply_to is None:
            request.setResponseCode(http.BAD_REQUEST)
            request.write('Invalid in_reply_to value')
            request.finish()
            return

        reply_to_mdh = MessageMetadataHelper(self.vumi_api, reply_to)
        if reply_to_mdh.get_conversation_key() != conversation.key:
            request.setResponseCode(http.BAD_REQUEST)
            request.write('Invalid in_reply_to value')
            request.finish()
            return

        msg_options = self.get_msg_options(payload,
                                           ['session_event', 'content'])
        content = msg_options.pop('content')
        continue_session = (msg_options.pop('session_event', None)
                            != TransportUserMessage.SESSION_CLOSE)
        helper_metadata = conversation.set_go_helper_metadata()
        helper_metadata.update(self.get_load_balancer_metadata(payload))

        msg = yield self.worker.reply_to(
            reply_to, content, continue_session,
            helper_metadata=helper_metadata)

        request.setResponseCode(http.OK)
        request.write(msg.to_json())
        request.finish()

    @inlineCallbacks
    def handle_PUT_send_to(self, request, payload):
        user_account = request.getUser()
        conversation = yield self.get_conversation(user_account)

        msg_options = self.get_msg_options(payload, ['content', 'to_addr'])
        to_addr = msg_options.pop('to_addr')
        content = msg_options.pop('content')
        msg_options['helper_metadata'] = conversation.set_go_helper_metadata()

        msg = yield self.worker.send_to(
            to_addr, content, endpoint='default', **msg_options)

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
        store = conversation.config.get('http_api', {}).get(
            'metrics_store', self.DEFAULT_STORE_NAME)
        for name, value, agg_class in metrics:
            self.worker.publish_account_metric(user_account, store, name,
                                               value, agg_class)

        request.finish()


class ConversationResource(resource.Resource):

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.redis = worker.redis
        self.conversation_key = conversation_key

    def get_worker_config(self, user_account_key):
        ctxt = ConfigContext(user_account=user_account_key)
        return self.worker.get_config(msg=None, ctxt=ctxt)

    def key(self, *args):
        return ':'.join(['concurrency'] + map(unicode, args))

    @inlineCallbacks
    def is_allowed(self, config, user_id):
        if config.concurrency_limit < 0:
            returnValue(True)
        count = int((yield self.redis.get(self.key(user_id))) or 0)
        returnValue(count < config.concurrency_limit)

    def track_request(self, user_id):
        return self.redis.incr(self.key(user_id))

    def release_request(self, err, user_id):
        return self.redis.decr(self.key(user_id))

    def render(self, request):
        return resource.NoResource().render(request)

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
        config = yield self.get_worker_config(user_id)
        if (yield self.is_allowed(config, user_id)):

            # remove track when request is closed
            finished = request.notifyFinish()
            finished.addBoth(self.release_request, user_id)

            yield self.track_request(user_id)
            returnValue(stream_class(self.worker, self.conversation_key))
        returnValue(resource.ErrorPage(http.FORBIDDEN, 'Forbidden',
                                       'Too many concurrent connections'))


class AuthorizedResource(resource.Resource):

    resource_class = ConversationResource

    def __init__(self, worker):
        resource.Resource.__init__(self)
        self.worker = worker

    def render(self, request):
        return resource.NoResource().render(request)

    def getChild(self, conversation_key, request):
        if conversation_key:
            res = self.resource_class(self.worker, conversation_key)
            checker = ConversationAccessChecker(self.worker.vumi_api,
                                                conversation_key)
            realm = ConversationRealm(res)
            p = portal.Portal(realm, [checker])

            factory = BasicCredentialFactory("Conversation Realm")
            protected_resource = HTTPAuthSessionWrapper(p, [factory])

            return protected_resource
        else:
            return resource.NoResource()
