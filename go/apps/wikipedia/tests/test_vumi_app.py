from twisted.internet.defer import inlineCallbacks
from vumi_wikipedia.tests import test_wikipedia as tw
from vumi_wikipedia.tests.test_wikipedia_api import (
    FakeHTTPTestCaseMixin, WIKIPEDIA_RESPONSES)

from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.wikipedia.vumi_app import WikipediaApplication


class TestWikipediaApplication(AppWorkerTestCase, FakeHTTPTestCaseMixin):
    application_class = WikipediaApplication
    transport_type = u'ussd'

    @inlineCallbacks
    def setUp(self):
        super(TestWikipediaApplication, self).setUp()
        yield self.start_webserver(WIKIPEDIA_RESPONSES)

        self.config = self.mk_config({})
        self.app = yield self.get_application(self.config)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)
        yield self.setup_tagpools()

    @inlineCallbacks
    def tearDown(self):
        yield self.stop_webserver()
        yield super(TestWikipediaApplication, self).tearDown()

    @inlineCallbacks
    def setup_conv(self, config={}):
        config.setdefault('api_url', self.url)
        self.conv = yield self.create_conversation(
            delivery_tag_pool=u'pool', delivery_class=self.transport_type,
            config=config)
        yield self.start_conversation(self.conv)

    def get_outbound_msgs(self, endpoint):
        return [m for m in self.get_dispatched_outbound()
                if m['routing_metadata']['endpoint_name'] == endpoint]

    @inlineCallbacks
    def assert_response(self, text, expected, session_event=None):
        yield self.dispatch_to_conv(
            self.mkmsg_in(text, session_event=session_event), self.conv)
        self.assertEqual(
            expected, self.get_outbound_msgs('default')[-1]['content'])

    def start_session(self):
        return self.assert_response(
            None, 'What would you like to search Wikipedia for?')

    @inlineCallbacks
    def test_happy_flow(self):
        yield self.setup_conv()
        yield self.start_session()
        yield self.assert_response('cthulhu', tw.CTHULHU_RESULTS)
        yield self.assert_response('1', tw.CTHULHU_SECTIONS)
        yield self.assert_response('2', tw.CTHULHU_USSD)

        [sms_msg] = self.get_outbound_msgs('sms_content')
        self.assertEqual(tw.CTHULHU_SMS, sms_msg['content'])
        self.assertEqual('+41791234567', sms_msg['to_addr'])
