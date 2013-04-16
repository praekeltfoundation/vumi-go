import base64

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.server import NOT_DONE_YET

from vumi.tests.utils import MockHttpServer
from vumi.transports.tests.utils import TransportTestCase

from go.vumitools.transports.vumi_bridge import GoConversationTransport


class GoConversationTransportTestCase(TransportTestCase):
    transport_class = GoConversationTransport

    @inlineCallbacks
    def setUp(self):
        yield super(GoConversationTransportTestCase, self).setUp()
        self.mock_server = MockHttpServer(self.handle_inbound_request)
        yield self.mock_server.start()
        config = self.mk_config({
            'base_url': self.mock_server.url,
            'account_key': 'account-key',
            'conversation_key': 'conversation-key',
            'access_token': 'access-token'
        })
        self.transport = yield self.get_transport(config)
        self._pending_reqs = []

    @inlineCallbacks
    def tearDown(self):
        yield super(GoConversationTransportTestCase, self).tearDown()
        for req in self._pending_reqs:
            if not req.finished:
                yield req.finish()
        yield self.mock_server.stop()

    def handle_inbound_request(self, request):
        self.mock_server.queue.put(request)
        return NOT_DONE_YET

    @inlineCallbacks
    def get_next_request(self):
        req = yield self.mock_server.queue.get()
        self._pending_reqs.append(req)
        returnValue(req)

    @inlineCallbacks
    def test_auth_headers(self):
        message_req = yield self.get_next_request()
        event_req = yield self.get_next_request()
        [msg_auth_header] = message_req.requestHeaders.getRawHeaders(
            'Authorization')
        self.assertEqual(msg_auth_header, 'Basic %s' % (
            base64.b64encode('account-key:access-token')))
        [event_auth_header] = event_req.requestHeaders.getRawHeaders(
            'Authorization')
        self.assertEqual(event_auth_header, 'Basic %s' % (
            base64.b64encode('account-key:access-token')))

    @inlineCallbacks
    def test_req_path(self):
        message_req = yield self.get_next_request()
        event_req = yield self.get_next_request()
        self.assertEqual(
            set([message_req.path, event_req.path]),
            set(['/conversation-key/messages.json',
                '/conversation-key/events.json']))
