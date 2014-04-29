import sys
from twisted.python import usage
from twisted.internet import reactor
from twisted.internet.defer import (
    maybeDeferred, Deferred, DeferredQueue, inlineCallbacks, returnValue)
from twisted.internet.task import deferLater
from vumi.service import Worker, WorkerCreator
from vumi.servicemaker import VumiOptions
import yaml

from go.apps.jsbox.outbound import mk_inbound_push_trigger
from go.apps.jsbox.utils import jsbox_js_config
from go.vumitools.api import VumiApi


class ScriptError(Exception):
    """
    An error to be caught and displayed nicely by a script handler.
    """


class JsBoxSendOptions(VumiOptions):
    optParameters = [
        ["user-account-key", None, None,
         "User account that owns the conversation."],
        ["conversation-key", None, None,
         "Conversation to send messages to."],
        ["vumigo-config", None, None,
         "File containing persistence configuration."],
        ["hz", None, "60.0",
         "Maximum number of messages to send per second."],
    ]

    def postOptions(self):
        VumiOptions.postOptions(self)
        if not self['vumigo-config']:
            raise usage.UsageError(
                "Please provide the vumigo-config parameter.")
        if not self['user-account-key']:
            raise usage.UsageError(
                "Please provide the user-account-key parameter.")
        if not self['conversation-key']:
            raise usage.UsageError(
                "Please provide the conversation-key parameter.")
        try:
            hz = float(self['hz'])
        except (TypeError, ValueError):
            hz_okay = False
        else:
            hz_okay = bool(hz > 0)
        if not hz_okay:
            raise usage.UsageError(
                "Please provide a positive float for hz")
        self['hz'] = hz

    def get_vumigo_config(self):
        with file(self['vumigo-config'], 'r') as stream:
            return yaml.safe_load(stream)


class Ticker(object):
    """
    An object that limits calls to a fixed number per second.

    :param float hz:
       Times per second that :meth:``tick`` may be called.
    """

    clock = reactor

    def __init__(self, hz):
        self._hz = hz
        self._min_dt = 1.0 / hz
        self._last = None

    def tick(self):
        d = Deferred()
        delay = 0
        if self._last is None:
            self._last = self.clock.seconds()
        else:
            now = self.clock.seconds()
            dt = now - self._last
            delay = 0 if (dt > self._min_dt) else (self._min_dt - dt)
            self._last = now
        self.clock.callLater(delay, d.callback, None)
        return d


class JsBoxSendWorker(Worker):

    WORKER_QUEUE = DeferredQueue()

    stdout = sys.stdout
    stderr = sys.stderr

    SUPPORTED_APPS = ('jsbox', 'dialogue')
    SEND_DELAY = 0.01  # No more than 100 msgs/second to the queue.

    def send_inbound_push_trigger(self, to_addr, conversation):
        self.emit('Starting %r -> %s' % (conversation, to_addr), err=True)
        msg = mk_inbound_push_trigger(to_addr, conversation)
        return self.send_to_conv(conversation, msg)

    @inlineCallbacks
    def send_jsbox(self, user_account_key, conversation_key, hz=60):
        conv = yield self.get_conversation(user_account_key, conversation_key)
        delivery_class = jsbox_js_config(conv.config).get('delivery_class')
        to_addrs = yield self.get_contact_addrs_for_conv(conv, delivery_class)
        ticker = Ticker(hz=hz)
        for to_addr in to_addrs:
            yield self.send_inbound_push_trigger(to_addr, conv)
            yield ticker.tick()

    @inlineCallbacks
    def get_contact_addrs_for_conv(self, conv, delivery_class):
        addrs = []
        for contacts in (yield conv.get_opted_in_contact_bunches(
                delivery_class)):
            for contact in (yield contacts):
                addrs.append(contact.addr_for(delivery_class))
        returnValue(addrs)

    @inlineCallbacks
    def send_to_conv(self, conv, msg):
        publisher = self._publishers[conv.conversation_type]
        yield publisher.publish_message(msg)
        # Give the reactor time to actually send the message.
        yield deferLater(reactor, self.SEND_DELAY, lambda: None)

    @inlineCallbacks
    def make_publisher(self, conv_type):
        routing_key = '%s_transport.inbound' % (conv_type,)
        self._publishers[conv_type] = yield self.publish_to(routing_key)

    @inlineCallbacks
    def get_conversation(self, user_account_key, conversation_key):
        user_api = self.vumi_api.get_user_api(user_account_key)
        conv = yield user_api.get_wrapped_conversation(conversation_key)
        if conv is None:
            raise ScriptError("Conversation not found: %s" % (
                conversation_key,))
        if conv.conversation_type not in self.SUPPORTED_APPS:
            raise ScriptError("Unsupported conversation type: %s" % (
                conv.conversation_type,))
        returnValue(conv)

    @inlineCallbacks
    def startWorker(self):
        self.vumi_api = yield VumiApi.from_config_async(
            self.config, self._amqp_client)
        self._publishers = {}
        for conv_type in self.SUPPORTED_APPS:
            yield self.make_publisher(conv_type)
        self.WORKER_QUEUE.put(self)

    def emit(self, obj, err=False):
        msg = '%s\n' % (obj,)
        if err:
            self.stderr.write(msg)
        else:
            self.stdout.write(msg)


@inlineCallbacks
def main(options):
    worker_creator = WorkerCreator(options.vumi_options)
    service = worker_creator.create_worker_by_class(
        JsBoxSendWorker, options.get_vumigo_config())
    service.startService()

    worker = yield JsBoxSendWorker.WORKER_QUEUE.get()
    yield worker.send_jsbox(
        options['user-account-key'], options['conversation-key'],
        hz=options['hz'])
    reactor.stop()


if __name__ == '__main__':
    try:
        options = JsBoxSendOptions()
        options.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    def _eb(f):
        f.printTraceback()

    def _main():
        maybeDeferred(main, options).addErrback(_eb)

    reactor.callLater(0, _main)
    reactor.run()
