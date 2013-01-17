import json

from twisted.internet.defer import Deferred
from twisted.internet import reactor
from twisted.web.client import Agent, ResponseDone
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
        self._response = None
        self._wait_for_response = Deferred()

    def get_response(self):
        return self._wait_for_response

    def handle_response(self, response):
        self._response = response
        if self._response.code == http.NO_CONTENT:
            self._wait_for_response.callback(self._response)
        else:
            self._response.deliverBody(self)

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
        # the PotentialDataLoss here is because Twisted didn't receive a
        # content length header, which is normal because we're streaming.
        if (reason.check(ResponseDone, http.PotentialDataLoss)
            and self._response is not None
            and not self._wait_for_response.called):
            self._wait_for_response.callback(self._response)
        else:
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
        receiver = VumiMessageReceiver(message_class, callback, errback)
        d = self.agent.request('GET', url, headers)
        d.addCallback(lambda response: receiver.handle_response(response))
        d.addErrback(log.err)
        return receiver
