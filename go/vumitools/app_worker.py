
from twisted.internet.defer import inlineCallbacks
from vumi import log
from vumi.application.base import ApplicationWorker
from go.vumitools.api import VumiApiEvent


class GoApplicationMixin(ApplicationWorker):

    @inlineCallbacks
    def _setup_go_event_publisher(self):
        self._go_event_publisher = yield self.publish_to('vumi.event')

    def publish_go_event(self, event_msg):
        self._go_event_publisher.publish_message(event_msg)

    def mkevent(self, event_type, content, conv_key, account_key):
        evt = VumiApiEvent.event(account_key, conv_key, event_type, content)
        return evt

    def fire_event(self, event_type, content, conv_key, account_key):
        evt = self.mkevent(event_type, content, conv_key, account_key)
        log.info("Firing event: %s" % evt)
        self.publish_go_event(evt)
