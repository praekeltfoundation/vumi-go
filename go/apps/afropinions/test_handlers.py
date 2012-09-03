import base64

from go.vumitools.tests.test_handler import EventHandlerTestCase

from vumi.tests.utils import LogCatcher, MockHttpServer

from twisted.internet.defer import inlineCallbacks


class YoPaymentHandlerTestCase(EventHandlerTestCase):

    handlers = [
        ('afropinions', 'go.apps.afropinions.YoPaymentHandler', {
            'poll_manager_prefix': 'vumigo.',
            'username': 'username',
            'password': 'password',
            'url': None,
            'method': 'POST',
            'amount': 1000,
            'reason': 'foo',
            })
    ]

    @inlineCallbacks
    def setUp(self):
        yield super(YoPaymentHandlerTestCase, self).setUp()
        self.track_event(self.account.key, self.conversation.key,
            'survey_completed', 'afropinions')

    @inlineCallbacks
    def test_hitting_url(self):
        msisdn = u'+2345'
        message_id = u'message-id'
        event = self.mkevent('survey_completed', {
            'from_addr': msisdn,
            'message_id': message_id,
            'transport_type': 'ussd',
            'participant': {
                'interactions': 2,
            }}, conv_key=self.conversation.key, account_key=self.account.key)


        self.mock_server = MockHttpServer()
        yield self.mock_server.start()

        handler = self.event_dispatcher.handlers['afropinions']
        handler.url = self.mock_server.url

        yield self.publish_event(event)
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
        handler = self.event_dispatcher.handlers['afropinions']
        auth = handler.get_auth_headers('username', 'password')
        credentials = base64.b64encode('username:password')
        self.assertEqual(auth, {
            'Authorization': 'Basic %s' % (credentials.strip(),)
            })
