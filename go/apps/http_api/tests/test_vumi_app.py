from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor

from vumi.middleware.tagger import TaggingMiddleware
from vumi.utils import http_request_full
from vumi.message import TransportUserMessage

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.api import VumiApi
from go.apps.http_api.vumi_app import StreamingHTTPWorker, Stream


class StreamingHTTPWorkerTestCase(AppWorkerTestCase):

    use_riak = True
    application_class = StreamingHTTPWorker

    @inlineCallbacks
    def setUp(self):
        yield super(StreamingHTTPWorkerTestCase, self).setUp()
        config = self.mk_config({
            'worker_name': 'foo',
            'web_path': '/foo',
            'web_port': 0,
            'metrics_prefix': 'foo',
            })
        self.app = yield self.get_application(config)
        self.addr = self.app.webserver.getHost()
        self.url = 'http://%s:%s%s' % (self.addr.host, self.addr.port,
                                        config['web_path'])

        # get the router to test
        self.vumi_api = yield VumiApi.from_config_async(config)
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)

        self.tag = ("pool", "tag")
        batch_id = yield self.vumi_api.mdb.batch_start([self.tag],
            user_account=unicode(self.account.key))
        self.conversation = yield self.create_conversation()
        self.conversation.batches.add_key(batch_id)
        yield self.conversation.save()

        self.patch(Stream, 'publish', self.patched_publish)

    def patched_publish(self, request, message):
        line = u'%s\n' % (message.to_json(),)
        request.write(line.encode('utf-8'))
        self.active_request = request

    @inlineCallbacks
    def test_messages_stream(self):
        msg1 = self.mkmsg_in(content='in 1',
                                message_id=TransportUserMessage.generate_id())
        TaggingMiddleware.add_tag_to_msg(msg1, self.tag)

        msg2 = self.mkmsg_in(content='in 2',
                                message_id=TransportUserMessage.generate_id())
        TaggingMiddleware.add_tag_to_msg(msg2, self.tag)

        url = '%s/%s/messages.js' % (self.url, self.conversation.key)
        d = http_request_full(url, method='GET')

        yield self.dispatch(msg1)
        yield self.dispatch(msg2)

        # This only works because we're actively closing the request captured
        # by patching the `publish` method on the `Stream` resource.
        self.active_request.finish()
        response = yield d
        self.assertTrue(msg1['message_id'] in response.delivered_body)
        self.assertTrue(msg2['message_id'] in response.delivered_body)
