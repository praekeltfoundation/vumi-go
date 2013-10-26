# -*- test-case-name: go.apps.http_api.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks

from vumi.config import ConfigInt, ConfigText
from vumi.transports.httprpc import httprpc

from go.vumitools.app_worker import GoApplicationWorker
from go.apps.http_api.resource import (AuthorizedResource,
                                       IncomingConversationResource)


class IncomingMessageWorkerConfig(GoApplicationWorker.CONFIG_CLASS):
    """Configuration options for StreamingHTTPWorker."""

    web_path = ConfigText(
        "The path the HTTP worker should expose the API on.",
        required=True, static=True)
    web_port = ConfigInt(
        "The port the HTTP worker should open for the API.",
        required=True, static=True)
    health_path = ConfigText(
        "The path the resource should receive health checks on.",
        default='/health/', static=True)


class IncomingHTTPWorker(GoApplicationWorker):

    worker_name = 'incoming_message_worker'
    CONFIG_CLASS = IncomingMessageWorkerConfig

    @inlineCallbacks
    def setup_application(self):
        yield super(IncomingHTTPWorker, self).setup_application()
        config = self.get_static_config()
        self.web_path = config.web_path
        self.web_port = config.web_port
        self.health_path = config.health_path
        self.metrics_prefix = config.metrics_prefix

        self.webserver = self.start_web_resources([
            (AuthorizedResource(self, IncomingConversationResource),
             self.web_path),
            (httprpc.HttpRpcHealthResource(self), self.health_path),
        ], self.web_port)

    def get_api_config(self, conversation, key):
        return conversation.config.get('http_api', {}).get(key)

    def get_health_response(self):
        return str("Um, something here")

    @inlineCallbacks
    def teardown_application(self):
        yield super(IncomingHTTPWorker, self).teardown_application()
        yield self.webserver.loseConnection()
