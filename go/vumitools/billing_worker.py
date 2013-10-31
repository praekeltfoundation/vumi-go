import decimal
import json

from urlparse import urljoin

from twisted.internet.defer import inlineCallbacks

from vumi import log
from vumi.dispatchers.endpoint_dispatchers import Dispatcher
from vumi.config import ConfigText
from vumi.utils import load_class_by_string, http_request_full

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin


class BillingApi(object):
    """Proxy to the billing REST API"""

    def __init__(self, base_url):
        self.base_url = base_url

    @inlineCallbacks
    def create_transaction(self, account_number, tag_pool_name,
                           tag_name, message_direction):
        """Create a new transaction for the given ``account_number``"""
        data = {
            'account_number': account_number,
            'tag_pool_name': tag_pool_name,
            'tag_name': tag_name,
            'message_direction': message_direction
        }

        url = urljoin(self.base_url, "/transactions")
        data = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        log.debug("Sending billing request to %r: %r" % (url, data))
        response = yield http_request_full(url, data, headers=headers)
        # TODO: Check for a non 200 response.code and do something
        log.debug("Got billing response: %r" % (response.delivered_body,))
        result = json.loads(response.delivered_body,
                            parse_float=decimal.Decimal)

        returnValue(result)


class BillingDispatcherConfig(Dispatcher.CONFIG_CLASS, GoWorkerConfigMixin):

    api_url = ConfigText(
        "Base URL of the billing REST API",
        static=True, required=True)

    billing_api = ConfigText(
        "Python path to the billing api proxy class",
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
        base_url = config.api_url
        cls_name = config.billing_api
        cls = load_class_by_string(cls_name)
        self.billing_api = cls(base_url)

    @inlineCallbacks
    def teardown_dispatcher(self):
        yield self._go_teardown_worker()
        yield super(BillingDispatcher, self).teardown_dispatcher()

    @inlineCallbacks
    def create_transaction_for_inbound(self, msg):
        msg_mdh = self.get_metadata_helper(msg)
        yield self.billing_api.create_transaction(
            msg_mdh.get_account_key(), msg_mdh.tag[0],
            msg_mdh.tag[1], self.MESSAGE_DIRECTION_INBOUND)

    @inlineCallbacks
    def create_transaction_for_outbound(self, msg):
        msg_mdh = self.get_metadata_helper(msg)
        yield self.billing_api.create_transaction(
            msg_mdh.get_account_key(), msg_mdh.tag[0],
            msg_mdh.tag[1], self.MESSAGE_DIRECTION_OUTBOUND)

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
