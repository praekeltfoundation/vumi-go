import json

from twisted.internet.defer import inlineCallbacks

from vumi import log
from vumi.dispatchers.endpoint_dispatchers import Dispatcher
from vumi.utils import http_request_full
from vumi.config import ConfigText

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin


class BillingDispatcherConfig(Dispatcher.CONFIG_CLASS, GoWorkerConfigMixin):

    transaction_create_url = ConfigText(
        "Billing API URL to create a new payment transaction",
        static=True, required=True)

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

    MESSAGE_DIRECTION_INBOUND = "Inbound"
    MESSAGE_DIRECTION_OUTBOUND = "Outbound"

    worker_name = 'billing_dispatcher'

    @inlineCallbacks
    def setup_dispatcher(self):
        yield super(BillingDispatcher, self).setup_dispatcher()
        yield self._go_setup_worker()
        config = self.get_static_config()
        self.transaction_create_url = config.transaction_create_url

    @inlineCallbacks
    def teardown_dispatcher(self):
        yield self._go_teardown_worker()
        yield super(BillingDispatcher, self).teardown_dispatcher()

    @inlineCallbacks
    def create_transaction_for_inbound(self, msg):
        data = {
            'account_number': "12345",
            'tag_pool_name': "test_pool",
            'message_direction': self.MESSAGE_DIRECTION_INBOUND
        }

        headers = {'Content-Type': 'application/json'}
        response = yield http_request_full(
            self.transaction_create_url, json.dumps(data), headers=headers)

        log.debug("Billing response: %r" % (response.delivered_body,))

    @inlineCallbacks
    def create_transaction_for_outbound(self, msg):
        data = {
            'account_number': "12345",
            'tag_pool_name': "test_pool",
            'message_direction': self.MESSAGE_DIRECTION_OUTBOUND
        }

        headers = {'Content-Type': 'application/json'}
        response = yield http_request_full(
            self.transaction_create_url, json.dumps(data), headers=headers)

        log.debug("Billing response: %r" % (response.delivered_body,))

    @inlineCallbacks
    def process_inbound(self, config, msg, connector_name):
        log.debug("Processing inbound: %r" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        yield self.create_transaction_for_inbound(msg)
        msg_mdh.set_paid()
        connector_name = self.get_configured_ro_connectors()[0]
        endpoint_name = msg.get_routing_endpoint()
        yield self.publish_inbound(msg, connector_name, endpoint_name)

    @inlineCallbacks
    def process_outbound(self, config, msg, connector_name):
        log.debug("Processing outbound: %r" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        yield self.create_transaction_for_outbound(msg)
        msg_mdh.set_paid()
        connector_name = self.get_configured_ri_connectors()[0]
        endpoint_name = msg.get_routing_endpoint()
        yield self.publish_outbound(msg, connector_name, endpoint_name)
