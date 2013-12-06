# -*- test-case-name: go.apps.http_api_nostream.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from twisted.internet.error import DNSLookupError
from twisted.web import http
from twisted.web.error import SchemeNotSupported

from vumi.config import ConfigInt, ConfigText
from vumi.utils import http_request_full, HttpTimeoutError
from vumi.transports.httprpc import httprpc
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker
from go.apps.http_api_nostream.resource import AuthorizedResource


class NoStreamingHTTPWorkerConfig(GoApplicationWorker.CONFIG_CLASS):
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
    concurrency_limit = ConfigInt(
        "Maximum number of clients per account. A value less than "
        "zero disables the limit",
        default=10)
    timeout = ConfigInt(
        "How long to wait for a response from a server when posting "
        "messages or events", default=5, static=True)


class NoStreamingHTTPWorker(GoApplicationWorker):

    worker_name = 'http_api_nostream_worker'
    CONFIG_CLASS = NoStreamingHTTPWorkerConfig

    @inlineCallbacks
    def setup_application(self):
        yield super(NoStreamingHTTPWorker, self).setup_application()
        config = self.get_static_config()
        self.web_path = config.web_path
        self.web_port = config.web_port
        self.health_path = config.health_path
        self.metrics_prefix = config.metrics_prefix

        # Set these to empty dictionaries because we're not interested
        # in using any of the helper functions at this point.
        self._event_handlers = {}
        self._session_handlers = {}

        self.webserver = self.start_web_resources([
            (AuthorizedResource(self), self.web_path),
            (httprpc.HttpRpcHealthResource(self), self.health_path),
        ], self.web_port)

    def get_api_config(self, conversation, key):
        return conversation.config.get('http_api_nostream', {}).get(key)

    @inlineCallbacks
    def consume_user_message(self, message):
        msg_mdh = self.get_metadata_helper(message)
        conversation = yield msg_mdh.get_conversation()
        if conversation is None:
            log.warning("Cannot find conversation for message: %r" % (
                message,))
            return

        push_message_url = self.get_api_config(conversation,
                                               'push_message_url')
        yield self.push(push_message_url, message)

    @inlineCallbacks
    def consume_unknown_event(self, event):
        """
        FIXME:  We're forced to do too much hoopla when trying to link events
                back to the conversation the original message was part of.
        """
        outbound_message = yield self.find_outboundmessage_for_event(event)
        if outbound_message is None:
            log.warning('Unable to find message %s for event %s.' % (
                event['user_message_id'], event['event_id']))

        config = yield self.get_message_config(event)
        conversation = config.get_conversation()
        push_event_url = self.get_api_config(conversation, 'push_event_url')
        yield self.push(push_event_url, event)

    @inlineCallbacks
    def push(self, url, vumi_message):
        config = self.get_static_config()
        data = vumi_message.to_json().encode('utf-8')
        try:
            resp = yield http_request_full(
                url.encode('utf-8'), data=data, headers={
                    'Content-Type': 'application/json; charset=utf-8',
                }, timeout=config.timeout)
            if resp.code != http.OK:
                log.warning('Got unexpected response code %s from %s' % (
                    resp.code, url))
        except SchemeNotSupported:
            log.warning('Unsupported scheme for URL: %s' % (url,))
        except HttpTimeoutError:
            log.warning("Timeout pushing message to %s" % (url,))
        except DNSLookupError:
            log.warning("DNS lookup error pushing message to %s" % (url,))

    def get_health_response(self):
        return "OK"

    @inlineCallbacks
    def teardown_application(self):
        yield super(NoStreamingHTTPWorker, self).teardown_application()
        yield self.webserver.loseConnection()
