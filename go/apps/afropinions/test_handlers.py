import base64

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase
from vumi.tests.utils import MockHttpServer

from go.apps.afropinions import YoPaymentHandler
from go.vumitools.tests.helpers import EventHandlerHelper


class TestYoPaymentHandler(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.eh_helper = self.add_helper(EventHandlerHelper())
        yield self.eh_helper.setup_event_dispatcher(
            'afropinions', YoPaymentHandler, {
                'poll_manager_prefix': 'vumigo.',
                'username': 'username',
                'password': 'password',
                'url': None,
                'method': 'POST',
                'amount': 1000,
                'reason': 'foo',
            })
        self.eh_helper.track_event('survey_completed', 'afropinions')

    @inlineCallbacks
    def test_hitting_url(self):
        msisdn = u'+2345'
        message_id = u'message-id'
        event = self.eh_helper.make_event('survey_completed', {
            'from_addr': msisdn,
            'message_id': message_id,
            'transport_type': 'ussd',
            'participant': {'interactions': 2},
        })

        self.mock_server = MockHttpServer()
        yield self.mock_server.start()

        self.eh_helper.get_handler('afropinions').url = self.mock_server.url

        yield self.eh_helper.dispatch_event(event)
        received_request = yield self.mock_server.queue.get()
        self.assertEqual(received_request.args['msisdn'][0], msisdn)
        self.assertEqual(received_request.args['amount'][0], '2000')
        self.assertEqual(received_request.args['reason'][0], 'foo')

        headers = received_request.requestHeaders
        self.assertEqual(headers.getRawHeaders('Content-Type'),
            ['application/x-www-form-urlencoded'])
        self.assertEqual(headers.getRawHeaders('Authorization'),
            ['Basic %s' % (base64.b64encode('username:password'),)])
        yield self.mock_server.stop()

    def test_auth_headers(self):
        handler = self.eh_helper.get_handler('afropinions')
        auth = handler.get_auth_headers('username', 'password')
        credentials = base64.b64encode('username:password')
        self.assertEqual(auth, {
            'Authorization': 'Basic %s' % (credentials.strip(),)
            })
