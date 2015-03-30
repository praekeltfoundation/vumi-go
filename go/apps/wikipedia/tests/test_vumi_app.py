from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from vumi_wikipedia.tests import test_wikipedia as tw
from vumi_wikipedia.tests.test_wikipedia_api import (
    FakeHTTPTestCaseMixin, WIKIPEDIA_RESPONSES)

from go.apps.tests.helpers import AppWorkerHelper
from go.apps.wikipedia.vumi_app import WikipediaApplication
from go.vumitools.metrics import get_conversation_metric_prefix


class TestWikipediaApplication(VumiTestCase, FakeHTTPTestCaseMixin):

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(
            AppWorkerHelper(WikipediaApplication))
        self.app = yield self.app_helper.get_app_worker({
            "secret_key": "s3cr3t",
        })
        self.fake_api = self.start_webserver(WIKIPEDIA_RESPONSES)

    @inlineCallbacks
    def setup_conv(self, config={}):
        config.setdefault('api_url', self.fake_api.url)
        self.conv = yield self.app_helper.create_conversation(config=config)
        yield self.app_helper.start_conversation(self.conv)

    def get_outbound_msgs(self, endpoint):
        return [m for m in self.app_helper.get_dispatched_outbound()
                if m['routing_metadata']['endpoint_name'] == endpoint]

    @inlineCallbacks
    def assert_response(self, text, expected, session_event=None):
        yield self.app_helper.make_dispatch_inbound(
            text, session_event=session_event, conv=self.conv)
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

        metric_names = [name for name, _ in
                        self.app_helper.get_published_metrics(self.app)]
        prefix = get_conversation_metric_prefix(self.conv)
        self.assertEqual(metric_names, ["%s%s" % (prefix, name)for name in [
            'wikipedia_search_call', 'wikipedia_extract_call',
            'wikipedia_extract_call']])

    @inlineCallbacks
    def test_conversation_config(self):
        yield self.setup_conv({
            'api_url': 'http://wikipedia/api.php',
            'include_url_in_sms': True,
            'mobi_url_host': 'http://mobi/',
            'shortening_api_url': 'http://wtxt.io/',
            'transliterate_unicode': True,
        })
        msg = self.app_helper.make_inbound(None, conv=self.conv)
        config = yield self.app.get_config(msg)
        self.assertEqual(config.api_url.geturl(), 'http://wikipedia/api.php')
        self.assertEqual(config.include_url_in_sms, True)
        self.assertEqual(config.mobi_url_host, 'http://mobi/')
        self.assertEqual(config.shortening_api_url.geturl(), 'http://wtxt.io/')
        self.assertEqual(config.transliterate_unicode, True)
