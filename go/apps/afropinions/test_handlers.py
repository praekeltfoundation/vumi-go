import base64

from go.vumitools.tests.test_handler import EventHandlerTestCase

from vumi.tests.utils import LogCatcher

from twisted.internet.defer import inlineCallbacks


class YoPaymentHandlerTestCase(EventHandlerTestCase):

    handlers = [
        ('afropinions', 'go.apps.afropinions.YoPaymentHandler', {
            'poll_manager_prefix': 'vumigo.',
            'username': 'username',
            'password': 'password',
            'url': None,
            'method': 'post',
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
            }, conv_key=self.conversation.key, account_key=self.account.key)

        with LogCatcher() as log:
            yield self.publish_event(event)
            [error] = log.errors
            self.assertTrue('No URL configured' in error['message'][0])

    def test_auth_headers(self):
        handler = self.event_dispatcher.handlers['afropinions']
        auth = handler.get_auth_headers('username', 'password')
        credentials = base64.b64encode('username:password')
        self.assertEqual(auth, {
            'Authorization': 'Basic %s' % (credentials.strip(),)
            })
