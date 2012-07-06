

from vumi import log

class EventHandler(object):
    def __init__(self, config):
        self.config = config

    def setup_handler(self):
        pass

    def handle_event(self, event, handler_config):
        raise NotImplementedError()


