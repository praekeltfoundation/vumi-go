# -*- test-case-name: go.vumitools.transports.vumi_bridge.tests.test_vumi_bridge -*-

from vumi.transports import Transport
from vumi.config import ConfigText
from vumi.message import TransportUserMessage, TransportEvent
from vumi import log

from go.apps.http_api.client import StreamingClient


class VumiBridgeTransportConfig(Transport.CONFIG_CLASS):
    account_key = ConfigText(
        'The account key to connect with.', static=True, required=True)
    conversation_key = ConfigText(
        'The conversation key to use.', static=True, required=True)
    access_token = ConfigText(
        'The access token for the conversation key.', static=True,
        required=True)


class GoConversationTransport(Transport):
    """
    This transport essentially connects as a client to Vumi Go's streaming
    HTTP API [1]_.

    It allows one to bridge Vumi and Vumi Go installations.

    .. [1] https://github.com/praekelt/vumi-go/blob/develop/docs/http_api.rst

    """

    transport_type = 'http'
    base_url = 'https://go.vumi.org/api/v1/go/http_api/'
    CONFIG_CLASS = VumiBridgeTransportConfig

    def setup_transport(self):
        self.client = StreamingClient()
        self.message_client = self.client.stream(
            TransportUserMessage, self.handle_inbound_message,
            log.error, self.get_url('messages.json'))
        self.event_client = self.client.stream(
            TransportEvent, self.handle_inbound_event,
            log.error, self.get_url('events.json'))

    def get_url(self, path):
        config = self.get_static_config()
        return '/'.join([self.base_url, config.conversation_key, path])

    def teardown_transport(self):
        pass

    def handle_outbound_message(self):
        pass

    def handle_inbound_message(self):
        pass

    def handle_inbound_event(self):
        pass
