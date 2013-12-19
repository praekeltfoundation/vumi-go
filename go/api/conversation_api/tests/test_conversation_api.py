import base64
import urllib

from mock import Mock
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.web import http

from vumi.utils import http_request_full
from vumi.tests.helpers import VumiTestCase

from go.api.conversation_api.conversation_api import (
    ConversationApiWorker, ConversationConfigResource)
from go.vumitools.tests.helpers import VumiApiHelper


class TestConversationApi(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())

        response = Mock()
        response.code = http.OK
        response.delivered_body = 'javascript!'
        self.mocked_url_call = Mock(
            side_effect=[succeed(response), succeed(response)])

        self.patch(ConversationConfigResource, 'load_source_from_url',
                   self.mocked_url_call)

        self.config = self.vumi_helper.mk_config({
            'worker_name': 'conversation_api_worker',
            'web_path': '/foo/',
            'web_port': 0,
            'health_path': '/health/',
        })
        self.worker = yield self.vumi_helper.get_worker_helper().get_worker(
            ConversationApiWorker, self.config)
        self.addr = self.worker.webserver.getHost()
        self.url = 'http://%s:%s%s' % (
            self.addr.host, self.addr.port, self.config['web_path'])

        self.user_helper = yield self.vumi_helper.make_user(u'user')
        yield self.vumi_helper.setup_tagpool(u"pool", [u"tag1", u"tag2"])
        yield self.user_helper.add_tagpool_permission(u"pool")

        self.conversation = yield self.user_helper.create_conversation(
            u'jsbox', config={
                'jsbox_app_config': {
                    'config': {'source_url': 'http://configsourcecode/'},
                },
                'jsbox': {
                    'source_url': 'http://sourcecode/',
                },
                'http_api': {
                    'api_tokens': ['token-1', 'token-2', 'token-3'],
                    'metrics_store': 'metrics_store'
                },
            })

        self.auth_headers = {
            'Authorization': [
                'Basic ' + base64.b64encode(
                    '%s:%s' % (self.user_helper.account_key, 'token-1'))
            ],
        }

    def get_conversation_url(self, *args, **kwargs):
        return '%s%s?%s' % (
            self.url,
            '/'.join(map(str, args)),
            urllib.urlencode(kwargs),
        )

    @inlineCallbacks
    def test_invalid_auth(self):
        resp = yield http_request_full(
            self.get_conversation_url(self.conversation.key), data='',
            method='GET', headers={})
        self.assertEqual(resp.code, http.UNAUTHORIZED)

    @inlineCallbacks
    def test_valid_auth(self):
        resp = yield http_request_full(
            self.get_conversation_url(self.conversation.key), data='',
            method='GET', headers=self.auth_headers)
        self.assertNotEqual(resp.code, http.UNAUTHORIZED)

    @inlineCallbacks
    def test_bad_command(self):
        resp = yield http_request_full(
            self.get_conversation_url(
                self.conversation.key, 'config'), headers=self.auth_headers)
        self.assertEqual(resp.code, http.NOT_FOUND)

        resp = yield http_request_full(
            self.get_conversation_url(
                self.conversation.key, 'config', 'foo', 'bar'),
            headers=self.auth_headers)
        self.assertEqual(resp.code, http.NOT_FOUND)

        resp = yield http_request_full(
            self.get_conversation_url(
                self.conversation.key, 'config', 'foo'),
            headers=self.auth_headers)
        self.assertEqual(resp.code, http.BAD_REQUEST)

    @inlineCallbacks
    def test_postcommit(self):
        resp = yield http_request_full(
            self.get_conversation_url(
                self.conversation.key, 'config', 'postcommit',
                foo="bar", baz=1),
            data='pickles', method='POST', headers=self.auth_headers)
        self.assertEqual(resp.code, http.OK)
        args, kwargs = self.mocked_url_call.call_args
        [url] = args
        self.assertEqual(args, ('http://sourcecode/',))
        self.assertEqual(kwargs, {'method': 'GET'})
        conv = yield self.user_helper.user_api.get_wrapped_conversation(
            self.conversation.key)
        conv_config = conv.get_config()
        self.assertEqual(conv_config['jsbox'], {
            'source_url': 'http://sourcecode/',
            'javascript': 'javascript!',
        })
        self.assertEqual(conv_config['jsbox_app_config'], {
            'config': {
                'source_url': 'http://configsourcecode/',
                'value': 'javascript!'
            }
        })
