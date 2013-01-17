import json

from twisted.internet.defer import inlineCallbacks, Deferred, DeferredQueue
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.protocols import basic
from twisted.python.failure import DefaultException

from vumi.middleware.tagger import TaggingMiddleware
from vumi.message import Message, TransportUserMessage, TransportEvent
from vumi import log

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.api import VumiApi
from go.apps.http_api.vumi_app import StreamingHTTPWorker


class VumiMessageReceiver(basic.LineReceiver):

    delimiter = '\n'
    message_class = Message

    def lineReceived(self, line):
        d = Deferred()
        d.addCallback(self.onMessage)
        d.addErrback(self.onError)
        line = line.strip()
        try:
            data = json.loads(line)
            d.callback(self.message_class(_process_fields=True, **data))
        except ValueError, e:
            d.errback(e)

    def connectionLost(self, reason):
        d = Deferred()
        d.addErrback(self.onError)
        d.errback(DefaultException(reason.getErrorMessage()))

    def onMessage(self, message):
        raise NotImplementedError('Subclasses should implement this.')

    def onError(self, failure):
        raise NotImplementedError('Subclasses should implement this.')

    def disconnect(self):
        self.transport._producer.loseConnection()
        self.transport._stopProxying()


class TransportUserMessageReceiver(VumiMessageReceiver):
    message_class = TransportUserMessage

    def __init__(self):
        self.inbox = DeferredQueue()
        self.errors = DeferredQueue()

    def onMessage(self, message):
        self.inbox.put(message)

    def onError(self, failure):
        self.errors.put(failure)


class TransportEventReceiver(TransportUserMessageReceiver):
    message_class = TransportEvent


class StreamingClient(object):

    def __init__(self):
        self.agent = Agent(reactor)

    def stream(self, receiver, url, headers={}):
        d = self.agent.request('GET', url, Headers(headers))
        d.addCallback(lambda response: response.deliverBody(receiver))
        d.addErrback(log.err)


class StreamingHTTPWorkerTestCase(AppWorkerTestCase):

    use_riak = True
    application_class = StreamingHTTPWorker

    @inlineCallbacks
    def setUp(self):
        yield super(StreamingHTTPWorkerTestCase, self).setUp()
        config = self.mk_config({
            'worker_name': 'foo',
            'web_path': '/foo',
            'web_port': 0,
            'metrics_prefix': 'foo',
            })
        self.app = yield self.get_application(config)
        self.addr = self.app.webserver.getHost()
        self.url = 'http://%s:%s%s' % (self.addr.host, self.addr.port,
                                        config['web_path'])

        # get the router to test
        self.vumi_api = yield VumiApi.from_config_async(config)
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)

        self.tag = ("pool", "tag")
        self.batch_id = yield self.vumi_api.mdb.batch_start([self.tag],
                                    user_account=unicode(self.account.key))
        self.conversation = yield self.create_conversation()
        self.conversation.batches.add_key(self.batch_id)
        yield self.conversation.save()

        self.client = StreamingClient()

    def dispatch_with_tag(self, msg, tag=None):
        if tag:
            TaggingMiddleware.add_tag_to_msg(msg, tag)
        return self.dispatch(msg)

    @inlineCallbacks
    def test_messages_stream(self):
        url = '%s/%s/messages.js' % (self.url, self.conversation.key)

        receiver = TransportUserMessageReceiver()
        self.client.stream(receiver, url)

        msg1 = self.mkmsg_in(content='in 1', message_id='1')
        yield self.dispatch_with_tag(msg1, self.tag)

        msg2 = self.mkmsg_in(content='in 2', message_id='2')
        yield self.dispatch_with_tag(msg2, self.tag)

        rm1 = yield receiver.inbox.get()
        rm2 = yield receiver.inbox.get()
        receiver.disconnect()

        self.assertEqual(msg1['message_id'], rm1['message_id'])
        self.assertEqual(msg2['message_id'], rm2['message_id'])
        self.assertEqual(receiver.errors.size, None)

    @inlineCallbacks
    def test_events_stream(self):
        url = '%s/%s/events.js' % (self.url, self.conversation.key)

        receiver = TransportEventReceiver()
        self.client.stream(receiver, url)

        msg1 = self.mkmsg_in(content='in 1', message_id='1')
        yield self.vumi_api.mdb.add_outbound_message(msg1,
                                                        batch_id=self.batch_id)
        ack1 = self.mkmsg_ack(user_message_id=msg1['message_id'])
        yield self.dispatch_event(ack1)

        msg2 = self.mkmsg_in(content='in 1', message_id='2')
        yield self.vumi_api.mdb.add_outbound_message(msg2,
                                                        batch_id=self.batch_id)
        ack2 = self.mkmsg_ack(user_message_id=msg2['message_id'])
        yield self.dispatch_event(ack2)

        ra1 = yield receiver.inbox.get()
        ra2 = yield receiver.inbox.get()
        receiver.disconnect()

        self.assertEqual(ack1['event_id'], ra1['event_id'])
        self.assertEqual(ack2['event_id'], ra2['event_id'])
        self.assertEqual(receiver.errors.size, None)
