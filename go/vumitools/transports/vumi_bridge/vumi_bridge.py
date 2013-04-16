# -*- test-case-name: go.vumitools.transports.vumi_bridge.tests.test_vumi_bridge -*-

import base64

from twisted.web.http_headers import Headers

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
    base_url = ConfigText(
        'The base URL for the API', static=True,
        default='https://go.vumi.org/api/v1/go/http_api/')


class GoConversationTransport(Transport):
    """
    This transport essentially connects as a client to Vumi Go's streaming
    HTTP API [1]_.

    It allows one to bridge Vumi and Vumi Go installations.

    .. [1] https://github.com/praekelt/vumi-go/blob/develop/docs/http_api.rst

    """

    transport_type = 'http'
    CONFIG_CLASS = VumiBridgeTransportConfig

    def setup_transport(self):
        self.client = StreamingClient()
        self.connect_api_clients()

    def connect_api_clients(self):
        self.message_client = self.client.stream(
            TransportUserMessage, self.handle_inbound_message,
            log.error, self.get_url('messages.json'),
            headers=self.get_auth_headers(),
            on_disconnect=self.reconnect_api_clients)
        self.event_client = self.client.stream(
            TransportEvent, self.handle_inbound_event,
            log.error, self.get_url('events.json'),
            headers=self.get_auth_headers(),
            on_disconnect=self.reconnect_api_clients)

    def reconnect_api_clients(self, reason):
        self.disconnect_api_clients()
        self.connect_api_clients()

    def disconnect_api_clients(self):
        self.message_client.disconnect()
        self.event_client.disconnect()

    def get_auth_headers(self):
        config = self.get_static_config()
        return Headers({
            'Authorization': ['Basic ' + base64.b64encode('%s:%s' % (
                config.account_key, config.access_token))],
        })

    def get_url(self, path):
        config = self.get_static_config()
        url = '/'.join([
            config.base_url.rstrip('/'), config.conversation_key, path])
        return url

    def teardown_transport(self):
        self.disconnect_api_clients()

    def handle_outbound_message(self):
        pass

    def handle_inbound_message(self, message):
        return self.publish_message(**message.payload)

    def handle_inbound_event(self):
        pass
