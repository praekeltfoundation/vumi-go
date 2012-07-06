

from vumi import log
from go.vumitools.api import VumiApiCommand


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

    def handle_event(self, event, handler_config):
        log.info(
            "SendMessageCommandHandler handling event: %s with config: %s" % (
            event, handler_config))
        sm_cmd = VumiApiCommand.command(
                handler_config['worker_name'],
                "send_message",
                send_message = event.payload['content'],
                conversation_key=handler_config['conversation_key'],
                )
        #print sm_cmd
        self.dispatcher.api_command_publisher.publish_message(sm_cmd)


