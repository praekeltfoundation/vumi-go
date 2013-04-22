import base64
import urllib

from twisted.internet.defer import inlineCallbacks, succeed
from twisted.web import http

from vumi.utils import http_request_full

from go.vumitools.api import VumiApi
from go.vumitools.tests.utils import AppWorkerTestCase
from go.api.conversation_api.conversation_api import (
    ConversationApiWorker, ConversationConfigResource)

from mock import Mock


class ConversationApiTestCase(AppWorkerTestCase):

    use_riak = True
    application_class = ConversationApiWorker
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        yield super(ConversationApiTestCase, self).setUp()

        response = Mock()
        response.code = http.OK
        response.delivered_body = 'javascript!'
        self.mocked_url_call = Mock(
            side_effect=[succeed(response), succeed(response)])

        self.patch(ConversationConfigResource, 'load_source_from_url',
                   self.mocked_url_call)

        self.config = self.mk_config({
            'worker_name': 'conversation_api_worker',
            'web_path': '/foo/',
            'web_port': 0,
            'health_path': '/health/',
        })
        self.app = yield self.get_application(self.config)
        self.addr = self.app.webserver.getHost()
        self.url = 'http://%s:%s%s' % (
            self.addr.host, self.addr.port, self.config['web_path'])

        # get the router to test
        self.vumi_api = yield VumiApi.from_config_async(self.config)
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)

        yield self.setup_tagpools()

        self.conversation = yield self.create_conversation()
        self.conversation.c.conversation_type = u'jsbox'
        yield self.conversation.save()

        self.conversation.c.delivery_tag_pool = u'pool'
        self.tag = yield self.conversation.acquire_tag()

        self.batch_id = yield self.vumi_api.mdb.batch_start(
            [self.tag], user_account=unicode(self.account.key))
        self.conversation.batches.add_key(self.batch_id)
        self.conversation.set_config({
            'jsbox_app_config': {
                'config': {
                    'source_url': 'http://configsourcecode/',
                }
            },
            'jsbox': {
                'source_url': 'http://sourcecode/',
            },
            'http_api': {
                'api_tokens': [
                    'token-1',
                    'token-2',
                    'token-3',
                ],
                'metrics_store': 'metrics_store'
            }
        })
        yield self.conversation.save()

        self.auth_headers = {
            'Authorization': [
                'Basic ' + base64.b64encode(
                    '%s:%s' % (self.account.key, 'token-1'))
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
        conv = yield self.user_api.get_wrapped_conversation(
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
