import base64
from datetime import datetime

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.server import NOT_DONE_YET

from vumi.tests.utils import MockHttpServer
from vumi.transports.tests.utils import TransportTestCase
from vumi.message import TransportUserMessage

from go.vumitools.transports.vumi_bridge import GoConversationTransport


class GoConversationTransportTestCase(TransportTestCase):

    transport_class = GoConversationTransport

    @inlineCallbacks
    def setUp(self):
        yield super(GoConversationTransportTestCase, self).setUp()
        self.mock_server = MockHttpServer(self.handle_inbound_request)
        yield self.mock_server.start()
        config = self.mk_config({
            'transport_name': self.transport_name,
            'base_url': self.mock_server.url,
            'account_key': 'account-key',
            'conversation_key': 'conversation-key',
            'access_token': 'access-token',
        })
        self.transport = yield self.get_transport(config)
        self._pending_reqs = []
        # when the transport fires up it stars two new connections,
        # wait for them & name them accordingly
        reqs = []
        reqs.append((yield self.get_next_request()))
        reqs.append((yield self.get_next_request()))
        if reqs[0].path.endswith('messages.json'):
            self.message_req = reqs[0]
            self.event_req = reqs[1]
        else:
            self.message_req = reqs[1]
            self.event_req = reqs[0]

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

    def test_auth_headers(self):
        [msg_auth_header] = self.message_req.requestHeaders.getRawHeaders(
            'Authorization')
        self.assertEqual(msg_auth_header, 'Basic %s' % (
            base64.b64encode('account-key:access-token')))
        [event_auth_header] = self.event_req.requestHeaders.getRawHeaders(
            'Authorization')
        self.assertEqual(event_auth_header, 'Basic %s' % (
            base64.b64encode('account-key:access-token')))

    def test_req_path(self):
        self.assertEqual(
            self.message_req.path,
            '/conversation-key/messages.json')
        self.assertEqual(
            self.event_req.path,
            '/conversation-key/events.json')

    @inlineCallbacks
    def test_receiving_messages(self):
        msg = self.mkmsg_in()
        msg['timestamp'] = datetime.utcnow()
        self.message_req.write(msg.to_json().encode('utf-8') + '\n')
        [received_msg] = yield self.wait_for_dispatched_messages(1)
        self.assertEqual(received_msg['message_id'], msg['message_id'])

    @inlineCallbacks
    def test_receiving_events(self):
        ack = self.mkmsg_ack()
        ack['event_id'] = 'event-id'
        ack['timestamp'] = datetime.utcnow()
        self.event_req.write(ack.to_json().encode('utf-8') + '\n')
        [received_ack] = yield self.wait_for_dispatched_events(1)
        self.assertEqual(received_ack['event_id'], ack['event_id'])

    @inlineCallbacks
    def test_sending_messages(self):
        msg = self.mkmsg_out()
        self.dispatch(msg)
        req = yield self.get_next_request()
        self.assertEqual(
            TransportUserMessage.from_json(req.content.read()),
            msg)
        req.finish()
