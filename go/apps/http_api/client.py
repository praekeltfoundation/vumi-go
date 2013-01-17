import json

from twisted.internet.defer import Deferred, DeferredQueue
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.protocols import basic
from twisted.python.failure import DefaultException

from vumi.message import Message, TransportUserMessage, TransportEvent
from vumi import log


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
