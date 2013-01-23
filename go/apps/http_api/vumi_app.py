# -*- test-case-name: go.apps.http_api.tests.test_vumi_app -*-
import json
import copy

from functools import partial

from zope.interface import implements

from twisted.cred import portal, checkers, credentials, error
from twisted.web import resource, http
from twisted.web.server import NOT_DONE_YET
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.guard import BasicCredentialFactory
from twisted.internet.error import ConnectionDone
from twisted.internet.defer import (Deferred, DeferredList, inlineCallbacks,
                                    returnValue)

from vumi.message import TransportUserMessage, TransportEvent
from vumi.errors import InvalidMessage
from vumi.transports.httprpc import httprpc
from vumi import log

from go.vumitools.api import VumiApi
from go.vumitools.app_worker import GoApplicationWorker


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

        # FIXME:    At some point this needs to be done better as it makes some
        #           assumption about how messages are routed which won't be
        #           true for very much longer.
        tag = (conversation.delivery_tag_pool, conversation.delivery_tag)
        msg_options = yield conversation.make_message_options(tag)

        payload = copy.deepcopy(tum.payload.copy())
        payload.update(msg_options)

        to_addr = payload.pop('to_addr')
        content = payload.pop('content')
        yield self.send_to(to_addr, content, **payload)
        request.setResponseCode(http.OK)
        request.finish()

    def send_to(self, to_addr, content, **payload):
        msg = TransportUserMessage.send(to_addr, content, **payload)
        return self.worker._publish_message(msg)

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

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.conversation_key = conversation_key

    def getChild(self, path, request):
        class_map = {
            'events.json': EventStream,
            'messages.json': MessageStream,
        }
        stream_class = class_map.get(path, lambda *a: resource.NoResource())
        return stream_class(self.worker, self.conversation_key)


class ConversationRealm(object):
    implements(portal.IRealm)

    def __init__(self, resource):
        self.resource = resource

    def requestAvatar(self, user, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, self.resource, lambda: None)
        raise NotImplementedError()


class ConversationAccessChecker(object):
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,)

    def __init__(self, vumi_api, conversation_key):
        self.vumi_api = vumi_api
        self.conversation_key = conversation_key

    @inlineCallbacks
    def requestAvatarId(self, credentials):
        username = credentials.username
        token = credentials.password
        user_exists = yield self.vumi_api.user_exists(username)
        if user_exists:
            user_api = self.vumi_api.get_user_api(username)
            conversation = yield user_api.get_wrapped_conversation(
                                                        self.conversation_key)
            if conversation is not None:
                metadata = conversation.get_metadata(default={})
                http_api_metadata = metadata.get('http_api', {})
                tokens = http_api_metadata.get('api_tokens', [])
                if token in tokens:
                    returnValue(username)
        raise error.UnauthorizedLogin()


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
    worker_name = 'http_api_worker'

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
        rk = stream_class.routing_key % {
            'transport_name': self.transport_name,
            'conversation_key': conversation_key,
            }
        return self.stream_publisher.publish_message(message, routing_key=rk)

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
        outbound_message = yield self.find_outboundmessage_for_event(event)
        if outbound_message is None:
            log.warning('Unable to find message %s for event %s.' % (
                event['user_message_id'], event['event_id']))
        batch = yield outbound_message.batch.get()
        account_key = batch.metadata['user_account']
        user_api = self.get_user_api(account_key)
        conversations = user_api.conversation_store.conversations
        mr = conversations.index_lookup('batches', batch.key)
        [conv_key] = yield mr.get_keys()
        yield self.stream(EventStream, conv_key, event)

    @inlineCallbacks
    def teardown_application(self):
        yield super(StreamingHTTPWorker, self).teardown_application()
        self.webserver.loseConnection()
