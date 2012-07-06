

from twisted.internet.defer import inlineCallbacks
from vumi import log
from go.vumitools.api import VumiApiCommand
from go.vumitools.conversation import ConversationStore


class EventHandler(object):
    def __init__(self, dispatcher, config):
        self.dispatcher = dispatcher
        self.config = config

    def setup_handler(self):
        pass

    def handle_event(self, event, handler_config):
        raise NotImplementedError()


class LoggingHandler(EventHandler):

    def handle_event(self, event, handler_config):
        log.info("LoggingHandler handling event: %s with config: %s" % (
            event, handler_config))

class SendMessageCommandHandler(EventHandler):

    @inlineCallbacks
    def handle_event(self, event, handler_config):
        log.info(
            "SendMessageCommandHandler handling event: %s with config: %s" % (
            event, handler_config))
        conv_store = ConversationStore(self.dispatcher.manager,
                                        event.payload['account_key'])
        conv = yield conv_store.get_conversation_by_key(
                                        event.payload['conversation_key'])
        batch_id = conv.batches.keys()[0]
        event.payload['content']['batch_id'] = batch_id
        event.payload['content']['msg_options'] = {}

        sm_cmd = VumiApiCommand.command(
                handler_config['worker_name'],
                "send_message",
                send_message = event.payload['content'],
                conversation_key=handler_config['conversation_key'],
                account_key=event.payload['account_key']
                )
        self.dispatcher.api_command_publisher.publish_message(sm_cmd)


