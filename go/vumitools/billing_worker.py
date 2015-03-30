import json
import urllib

from urlparse import urljoin

from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet import reactor

from vumi import log
from vumi.dispatchers.endpoint_dispatchers import Dispatcher
from vumi.config import ConfigText, ConfigFloat, ConfigBool
from vumi.message import TransportUserMessage
from vumi.utils import http_request_full

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin

from go.billing.utils import JSONEncoder, JSONDecoder, BillingError

SESSION_CLOSE = TransportUserMessage.SESSION_CLOSE
SESSION_NEW = TransportUserMessage.SESSION_NEW


class BillingApi(object):
    """Proxy to the billing REST API"""

    def __init__(self, base_url, retry_delay):
        self.base_url = base_url
        self.retry_delay = retry_delay

    @inlineCallbacks
    def _call_with_retry(self, url, data, headers, method):
        """
        Make an HTTP request and retry after a delay if it raises an exception.
        """
        try:
            response = yield http_request_full(
                url, data, headers=headers, method=method)
        except Exception:
            # Wait a bit and then retry. Only one retry here.
            d = Deferred()
            reactor.callLater(self.retry_delay, d.callback, None)
            yield d
            response = yield http_request_full(
                url, data, headers=headers, method=method)
        returnValue(response)

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
        response = yield self._call_with_retry(
            url, data, headers=headers, method=method)

        log.debug("Got billing response: %r" % (response.delivered_body,))
        if response.code != 200:
            raise BillingError(response.delivered_body)
        result = json.loads(response.delivered_body, cls=JSONDecoder)
        returnValue(result)

    def create_transaction(self, account_number, message_id, tag_pool_name,
                           tag_name, provider, message_direction,
                           session_created, transaction_type, session_length):
        """Create a new transaction for the given ``account_number``"""
        data = {
            'account_number': account_number,
            'message_id': message_id,
            'tag_pool_name': tag_pool_name,
            'tag_name': tag_name,
            'provider': provider,
            'message_direction': message_direction,
            'session_created': session_created,
            'transaction_type': transaction_type,
            'session_length': session_length,
        }
        return self._call_api("/transactions", data=data, method='POST')


class BillingDispatcherConfig(Dispatcher.CONFIG_CLASS, GoWorkerConfigMixin):

    api_url = ConfigText(
        "Base URL of the billing REST API",
        static=True, required=True)
    retry_delay = ConfigFloat(
        "Delay before retrying failed API calls, default 0.5s",
        static=True, default=0.5)
    disable_billing = ConfigBool(
        "Disable calling the billing API and just pass through all messages.",
        static=True, default=False)
    session_metadata_field = ConfigText(
        "Name of the session metadata field to look for in each message to "
        "calculate session length",
        static=True, default='session_metadata')
    credit_limit_message = ConfigText(
        "The message to send when terminating session based transports.",
        static=True, default='Vumi Go account has run out of credits.')

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

    TRANSACTION_TYPE_MESSAGE = "Message"

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
        self.billing_api = BillingApi(self.api_url, config.retry_delay)
        self.disable_billing = config.disable_billing
        self.session_metadata_field = config.session_metadata_field
        self.credit_limit_message = config.credit_limit_message

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

    @classmethod
    def determine_session_length(cls, session_metadata_field, msg):
        """
        Determines the length of the session from metadata attached to the
        message. The billing dispatcher looks for the following on the message
        payload to calculate this:

          - ``helper_metadata.<session_metadata_field>.session_start``
          - ``helper_metadata.<session_metadata_field>.session_end``

        If either of these fields are not present, the message is assumed to not
        contain enough information to calculate the session length and ``None``
        is returned
        """
        metadata = msg['helper_metadata'].get(session_metadata_field, {})

        if 'session_start' not in metadata:
            return None

        if 'session_end' not in metadata:
            return None

        return metadata['session_end'] - metadata['session_start']

    def _determine_session_length(self, msg):
        return self.determine_session_length(self.session_metadata_field, msg)

    @inlineCallbacks
    def create_transaction_for_inbound(self, msg):
        """Create a transaction for the given inbound message"""
        self.validate_metadata(msg)
        msg_mdh = self.get_metadata_helper(msg)
        session_created = msg['session_event'] == 'new'
        transaction = yield self.billing_api.create_transaction(
            account_number=msg_mdh.get_account_key(),
            message_id=msg['message_id'],
            tag_pool_name=msg_mdh.tag[0], tag_name=msg_mdh.tag[1],
            provider=msg.get('provider'),
            message_direction=self.MESSAGE_DIRECTION_INBOUND,
            session_created=session_created,
            transaction_type=self.TRANSACTION_TYPE_MESSAGE,
            session_length=self._determine_session_length(msg))
        returnValue(transaction)

    @inlineCallbacks
    def create_transaction_for_outbound(self, msg):
        """Create a transaction for the given outbound message"""
        self.validate_metadata(msg)
        msg_mdh = self.get_metadata_helper(msg)
        session_created = msg['session_event'] == 'new'
        transaction = yield self.billing_api.create_transaction(
            account_number=msg_mdh.get_account_key(),
            message_id=msg['message_id'],
            tag_pool_name=msg_mdh.tag[0], tag_name=msg_mdh.tag[1],
            provider=msg.get('provider'),
            message_direction=self.MESSAGE_DIRECTION_OUTBOUND,
            session_created=session_created,
            transaction_type=self.TRANSACTION_TYPE_MESSAGE,
            session_length=self._determine_session_length(msg))
        returnValue(transaction)

    @inlineCallbacks
    def process_inbound(self, config, msg, connector_name):
        """Process an inbound message.

        Any errors are logged and the message is allowed to continue on its
        path and fulfill its destiny.
        """
        log.debug("Processing inbound: %r" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        try:
            if self.disable_billing:
                log.info(
                    "Not billing for inbound message: %r" % msg.to_json())
            else:
                result = yield self.create_transaction_for_inbound(msg)
                if result.get('transaction'):
                    msg_mdh.set_paid()

        except BillingError:
            log.warning(
                "BillingError for inbound message, sending without billing:"
                " %r" % (msg,))
            log.err()
        except Exception:
            log.warning(
                "Error processing inbound message, sending without billing:"
                " %r" % (msg,))
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
            if self.disable_billing:
                log.info(
                    "Not billing for outbound message: %r" % msg.to_json())
            else:
                result = yield self.create_transaction_for_outbound(msg)
                if result.get('transaction'):
                    msg_mdh.set_paid()
                if result.get('credit_cutoff_reached', False):
                    msg = self._handle_credit_cutoff(msg)
        except BillingError:
            log.warning(
                "BillingError for outbound message, sending without billing:"
                " %r" % (msg,))
            log.err()
        except Exception:
            log.warning(
                "Error processing outbound message, sending without billing:"
                " %r" % (msg,))
            log.err()
        if msg is not None:
            yield self.publish_outbound(
                msg, self.receive_inbound_connector, None)

    def _handle_credit_cutoff(self, msg):
        session_event = msg.get('session_event')
        if session_event is not None and session_event != SESSION_NEW:
            msg['session_event'] = SESSION_CLOSE
            msg['content'] = self.credit_limit_message
            return msg
        else:
            return None

    @inlineCallbacks
    def process_event(self, config, event, connector_name):
        """Process an event message.

        Publish the event to the ``AccountRoutingTableDispatcher``.
        """
        log.debug("Processing event: %s" % (event,))
        yield self.publish_event(event, self.receive_outbound_connector, None)
