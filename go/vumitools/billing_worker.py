import json
import urllib

from urlparse import urljoin

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.dispatchers.endpoint_dispatchers import Dispatcher
from vumi.config import ConfigText
from vumi.utils import http_request_full

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin

from go.billing.utils import JSONEncoder, JSONDecoder, BillingError


class BillingApi(object):
    """Proxy to the billing REST API"""

    def __init__(self, base_url):
        self.base_url = base_url

    @inlineCallbacks
    def _call_api(self, path, query=None, data=None, method='GET'):
        """Perform the actual HTTP call to the billing API.

        If the HTTP response code is anything other than 200,
        raise a BillingError exception.
        """
        url = urljoin(self.base_url, path)
        if query:
            url = "%s?%s" % (url, urllib.urlencode(query))
        data = json.dumps(data, cls=JSONEncoder)
        headers = {'Content-Type': 'application/json'}
        log.debug("Sending billing request to %r: %r" % (url, data))
        response = yield http_request_full(url, data, headers=headers,
                                           method=method)

        log.debug("Got billing response: %r" % (response.delivered_body,))
        if response.code != 200:
            raise BillingError(response.delivered_body)
        result = json.loads(response.delivered_body, cls=JSONDecoder)
        returnValue(result)

    def create_transaction(self, account_number, message_id, tag_pool_name,
                           tag_name, message_direction, session_created):
        """Create a new transaction for the given ``account_number``"""
        data = {
            'account_number': account_number,
            'message_id': message_id,
            'tag_pool_name': tag_pool_name,
            'tag_name': tag_name,
            'message_direction': message_direction,
            'session_created': session_created,
        }
        return self._call_api("/transactions", data=data, method='POST')


class BillingDispatcherConfig(Dispatcher.CONFIG_CLASS, GoWorkerConfigMixin):

    api_url = ConfigText(
        "Base URL of the billing REST API",
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
        self.receive_inbound_connector = \
            self.get_configured_ri_connectors()[0]

        self.receive_outbound_connector = \
            self.get_configured_ro_connectors()[0]

        self.api_url = config.api_url
        self.billing_api = BillingApi(self.api_url)

    @inlineCallbacks
    def teardown_dispatcher(self):
        yield self._go_teardown_worker()
        yield super(BillingDispatcher, self).teardown_dispatcher()

    def validate_metadata(self, msg):
        msg_mdh = self.get_metadata_helper(msg)
        if not msg_mdh.has_user_account():
            raise BillingError(
                "No account number found for message %s" %
                (msg.get('message_id'),))

        if not msg_mdh.tag:
            raise BillingError(
                "No tag found for message %s" % (msg.get('message_id'),))

    @inlineCallbacks
    def create_transaction_for_inbound(self, msg):
        """Create a transaction for the given inbound message"""
        self.validate_metadata(msg)
        msg_mdh = self.get_metadata_helper(msg)
        session_created = msg['session_event'] == 'new'
        yield self.billing_api.create_transaction(
            account_number=msg_mdh.get_account_key(),
            message_id=msg['message_id'],
            tag_pool_name=msg_mdh.tag[0], tag_name=msg_mdh.tag[1],
            message_direction=self.MESSAGE_DIRECTION_INBOUND,
            session_created=session_created)

    @inlineCallbacks
    def create_transaction_for_outbound(self, msg):
        """Create a transaction for the given outbound message"""
        self.validate_metadata(msg)
        msg_mdh = self.get_metadata_helper(msg)
        session_created = msg['session_event'] == 'new'
        yield self.billing_api.create_transaction(
            account_number=msg_mdh.get_account_key(),
            message_id=msg['message_id'],
            tag_pool_name=msg_mdh.tag[0], tag_name=msg_mdh.tag[1],
            message_direction=self.MESSAGE_DIRECTION_OUTBOUND,
            session_created=session_created)

    @inlineCallbacks
    def process_inbound(self, config, msg, connector_name):
        """Process an inbound message.

        Any errors are logged and the message is allowed to continue on its
        path and fulfill its destiny.
        """
        log.debug("Processing inbound: %r" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        try:
            yield self.create_transaction_for_inbound(msg)
            msg_mdh.set_paid()
        except BillingError:
            log.err()
        yield self.publish_inbound(msg, self.receive_outbound_connector, None)

    @inlineCallbacks
    def process_outbound(self, config, msg, connector_name):
        """Process an outbound message.

        Any errors are logged and the message is allowed to continue on its
        path and fulfill its destiny.
        """
        log.debug("Processing outbound: %r" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        try:
            yield self.create_transaction_for_outbound(msg)
            msg_mdh.set_paid()
        except BillingError:
            log.err()
        yield self.publish_outbound(msg, self.receive_inbound_connector, None)

    @inlineCallbacks
    def process_event(self, config, event, connector_name):
        """Process an event message.

        Publish the event to the ``AccountRoutingTableDispatcher``.
        """
        log.debug("Processing event: %s" % (event,))
        yield self.publish_event(event, self.receive_outbound_connector, None)
