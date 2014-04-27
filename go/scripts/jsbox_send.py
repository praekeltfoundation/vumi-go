import sys
from twisted.python import usage
from twisted.internet import reactor
from twisted.internet.defer import (
    maybeDeferred, DeferredQueue, inlineCallbacks, returnValue)
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

    def get_vumigo_config(self):
        with file(self['vumigo-config'], 'r') as stream:
            return yaml.safe_load(stream)


class JsBoxSendWorker(Worker):

    WORKER_QUEUE = DeferredQueue()

    stdout = sys.stdout
    stderr = sys.stderr

    SUPPORTED_APPS = ('jsbox', 'dialogue')

    def send_inbound_push_trigger(self, to_addr, conversation):
        self.emit('Starting %r -> %s' % (conversation, to_addr), err=True)
        msg = mk_inbound_push_trigger(to_addr, conversation)
        return self.send_to_conv(conversation, msg)

    @inlineCallbacks
    def send_jsbox(self, user_account_key, conversation_key):
        conv = yield self.get_conversation(user_account_key, conversation_key)
        delivery_class = jsbox_js_config(conv.config).get('delivery_class')
        to_addrs = yield self.get_contact_addrs_for_conv(conv, delivery_class)
        for to_addr in to_addrs:
            yield self.send_inbound_push_trigger(to_addr, conv)

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
        publisher = yield self.get_conv_publisher(conv)
        yield publisher.publish_message(msg)

    @inlineCallbacks
    def get_conv_publisher(self, conv):
        conv_type = conv.conversation_type.encode('utf8')
        routing_key = '%s_transport.inbound' % (conv_type,)
        if routing_key not in self._publishers:
            self._publishers[routing_key] = yield self.publish_to(routing_key)
        returnValue(self._publishers[routing_key])

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
        self.WORKER_QUEUE.put(self)

    def emit(self, obj, err=False):
        msg = '%s\n' % (obj,)
        if err:
            self.stderr.write(msg)
        else:
            self.stdout.write(msg)


@inlineCallbacks
def main(options):
    quiet = options['quiet']

    worker_creator = WorkerCreator(options.vumi_options)
    worker_creator.create_worker_by_class(
        JsBoxSendWorker, options.get_vumigo_config())

    in_file = sys.stdin
    out_file = sys.stdout if not quiet else None

    worker = yield JsBoxSendWorker.WORKER_QUEUE.get()
    yield worker.process_file(in_file, out_file)
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
