import base64
import urllib

from twisted.internet.defer import inlineCallbacks, succeed
from twisted.web import http

from vumi.utils import http_request_full

from go.vumitools.api import VumiApi
from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.conversation_api.conversation_api import (
    ConversationApiWorker, ConversationConfigResource)


class FakeConversation(object):

    def __init__(self):
        self.args = None
        self.contents = None

    def update_configuration(self, args, contents):
        self.args = args
        self.contents = contents
        return succeed(1)


class ConversationApiTestCase(AppWorkerTestCase):

    use_riak = True
    application_class = ConversationApiWorker

    @inlineCallbacks
    def setUp(self):
        yield super(ConversationApiTestCase, self).setUp()

        self.mocked_conv = FakeConversation()
        self.patch(ConversationConfigResource, 'get_conversation',
                   lambda _, ua: self.mocked_conv)

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
        self.conversation.c.delivery_tag_pool = u'pool'
        self.tag = yield self.conversation.acquire_tag()

        self.batch_id = yield self.vumi_api.mdb.batch_start(
            [self.tag], user_account=unicode(self.account.key))
        self.conversation.batches.add_key(self.batch_id)
        self.conversation.set_metadata({
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
    def test_post_config(self):
        resp = yield http_request_full(
            self.get_conversation_url(self.conversation.key, 'config',
                                      foo="bar", baz=1),
            data='pickles', method='POST', headers=self.auth_headers)
        self.assertEqual(self.mocked_conv.args, {
            'foo': ['bar'],
            'baz': ['1']
        })
        self.assertEqual(resp.code, http.OK)
        self.assertEqual(self.mocked_conv.contents, 'pickles')
