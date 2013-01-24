# -*- test-case-name: go.apps.http_api.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks


from vumi.transports.httprpc import httprpc
from vumi import log

from go.vumitools.api import VumiApi
from go.vumitools.app_worker import GoApplicationWorker
from go.apps.http_api.resource import (StreamingResource, MessageStream,
                                        EventStream)


class StreamingHTTPWorker(GoApplicationWorker):
    """

    :param str web_path:
        The path the HTTP worker should expose the API on
    :param int web_port:
        The port the HTTP worker should open for the API
    :param str health_path:
        The path the resource should receive health checks on.
        Defaults to '/health/'
    """
    worker_name = 'http_api_worker'

    def validate_config(self):
        super(StreamingHTTPWorker, self).validate_config()
        self.web_path = self.config['web_path']
        self.web_port = int(self.config['web_port'])
        self.health_path = self.config.get('health_path', '/health/')

    @inlineCallbacks
    def setup_application(self):
        yield super(StreamingHTTPWorker, self).setup_application()
        # Set these to empty dictionaries because we're not interested
        # in using any of the helper functions at this point.
        self._event_handlers = {}
        self._session_handlers = {}
        self.vumi_api = yield VumiApi.from_config_async(self.config)
        # We do give the publisher a key but won't actually use it
        self.stream_publisher = yield self.publish_to(
            '%s.stream.lost_and_found' % (self.transport_name,))

        self.webserver = self.start_web_resources([
            (StreamingResource(self), self.web_path),
            (httprpc.HttpRpcHealthResource(self), self.health_path),
            ], self.web_port)

    def stream(self, stream_class, conversation_key, message):
        # Publish the message by manually specifying the routing key
        rk = stream_class.routing_key % {
            'transport_name': self.transport_name,
            'conversation_key': conversation_key,
            }
        return self.stream_publisher.publish_message(message, routing_key=rk)

    @inlineCallbacks
    def consume_user_message(self, message):
        md = self.get_go_metadata(message)
        conv_key, conv_type = yield md.get_conversation_info()
        yield self.stream(MessageStream, conv_key, message)

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
        batch = yield outbound_message.batch.get()
        account_key = batch.metadata['user_account']
        user_api = self.get_user_api(account_key)
        conversations = user_api.conversation_store.conversations
        mr = conversations.index_lookup('batches', batch.key)
        [conv_key] = yield mr.get_keys()
        yield self.stream(EventStream, conv_key, event)

    @inlineCallbacks
    def teardown_application(self):
        yield super(StreamingHTTPWorker, self).teardown_application()
        self.webserver.loseConnection()
