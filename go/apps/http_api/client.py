import json

from twisted.internet.defer import Deferred
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web import http
from twisted.protocols import basic
from twisted.python.failure import DefaultException

from vumi.message import Message
from vumi import log


class VumiMessageReceiver(basic.LineReceiver):

    delimiter = '\n'
    message_class = Message

    def __init__(self, message_class, callback, errback):
        self.message_class = message_class
        self.callback = callback
        self.errback = errback
        self.response = None
        self.deferred = Deferred()

    def handle_response(self, response):
        self.response = response
        if self.response.code == http.NO_CONTENT:
            self.deferred.callback(self.response)
        else:
            response.deliverBody(self)

    def lineReceived(self, line):
        d = Deferred()
        d.addCallback(self.callback)
        d.addErrback(self.errback)
        line = line.strip()
        try:
            data = json.loads(line)
            d.callback(self.message_class(_process_fields=True, **data))
        except ValueError, e:
            d.errback(e)

    def connectionLost(self, reason):
        d = Deferred()
        d.addErrback(self.errback)
        d.errback(DefaultException(reason.getErrorMessage()))

    def disconnect(self):
        if self.transport._producer is not None:
            self.transport._producer.loseConnection()
            self.transport._stopProxying()


class StreamingClient(object):

    def __init__(self):
        self.agent = Agent(reactor)

    def stream(self, message_class, callback, errback, url, headers=None):
        d = self.agent.request('GET', url, headers)
        d.addCallback(self.handle_response, message_class, callback, errback)
        d.addErrback(log.err)
        return d

    def handle_response(self, response, message_class, callback, errback):
        receiver = VumiMessageReceiver(message_class, callback, errback)
        receiver.handle_response(response)
        return receiver
