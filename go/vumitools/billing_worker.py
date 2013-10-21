from twisted.internet.defer import inlineCallbacks

from vumi import log
from vumi.dispatchers.endpoint_dispatchers import Dispatcher

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin


class BillingDispatcherConfig(Dispatcher.CONFIG_CLASS, GoWorkerConfigMixin):

    def post_validate(self):
        if len(self.receive_inbound_connectors) != 1:
            self.raise_config_error("There should be exactly one connector "
                                    "that receives inbound messages.")

        if len(self.receive_outbound_connectors) != 1:
            self.raise_config_error("There should be exactly one connector "
                                    "that receives outbound messages.")


class BillingDispatcher(Dispatcher, GoWorkerMixin):
    """Billing dispatcher class"""

    CONFIG_CLASS = BillingDispatcherConfig
    worker_name = 'billing_dispatcher'

    @inlineCallbacks
    def setup_dispatcher(self):
        yield self._go_setup_worker()
        self.unpause_connectors()

    @inlineCallbacks
    def teardown_dispatcher(self):
        yield self.pause_connectors()
        yield self._go_teardown_worker()

    def process_inbound(self, config, msg, connector_name):
        log.debug("Processing inbound: %r" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        # TODO: Create transaction by calling the billing API
        msg_mdh.set_paid()
        connector_name = self.get_configured_ro_connectors()[0]
        endpoint_name = msg.get_routing_endpoint()
        self.publish_inbound(msg, connector_name, endpoint_name)

    def process_outbound(self, config, msg, connector_name):
        log.debug("Processing outbound: %r" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        # TODO: Create transaction by calling the billing API
        msg_mdh.set_paid()
        connector_name = self.get_configured_ri_connectors()[0]
        endpoint_name = msg.get_routing_endpoint()
        self.publish_outbound(msg, connector_name, endpoint_name)
