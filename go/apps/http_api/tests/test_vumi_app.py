import base64
import json

from twisted.internet.defer import inlineCallbacks, DeferredQueue
from twisted.web.http_headers import Headers
from twisted.web import http

from vumi.utils import http_request_full
from vumi.middleware.tagger import TaggingMiddleware
from vumi.message import TransportUserMessage, TransportEvent

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.api import VumiApi

from go.apps.http_api.vumi_app import StreamingHTTPWorker
from go.apps.http_api.client import StreamingClient, VumiMessageReceiver
from go.apps.http_api.resource import ConversationResource


class TestMessageReceiver(VumiMessageReceiver):
    message_class = TransportUserMessage

    def __init__(self, *args, **kwargs):
        VumiMessageReceiver.__init__(self, *args, **kwargs)
        self.inbox = DeferredQueue()
        self.errors = DeferredQueue()

    def onMessage(self, message):
        self.inbox.put(message)

    def onError(self, failure):
        self.errors.put(failure)


class TestEventReceiver(TestMessageReceiver):
    message_class = TransportEvent


class StreamingHTTPWorkerTestCase(AppWorkerTestCase):

    use_riak = True
    application_class = StreamingHTTPWorker

    @inlineCallbacks
    def setUp(self):
        yield super(StreamingHTTPWorkerTestCase, self).setUp()
        self.config = self.mk_config({
            'worker_name': 'worker_name',
            'health_path': '/health/',
            'web_path': '/foo',
            'web_port': 0,
            'metrics_prefix': 'metrics_prefix.',
            })
        self.app = yield self.get_application(self.config)
        self.addr = self.app.webserver.getHost()
        self.url = 'http://%s:%s%s' % (self.addr.host, self.addr.port,
                                        self.config['web_path'])

        # get the router to test
        self.vumi_api = yield VumiApi.from_config_async(self.config)
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)

        yield self.setup_tagpools()

        self.conversation = yield self.create_conversation()
        self.conversation.c.delivery_tag_pool = u'pool'
        self.tag = yield self.conversation.acquire_tag()

        self.batch_id = yield self.vumi_api.mdb.batch_start([self.tag],
                                    user_account=unicode(self.account.key))
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
            'Authorization': ['Basic ' + base64.b64encode('%s:%s' % (
                self.account.key, 'token-1'))],
            }

        self.client = StreamingClient()

    def dispatch_with_tag(self, msg, tag=None):
        if tag:
            TaggingMiddleware.add_tag_to_msg(msg, tag)
        return self.dispatch(msg)

    @inlineCallbacks
    def test_messages_stream(self):
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)

        messages = DeferredQueue()
        errors = DeferredQueue()
        receiver = self.client.stream(TransportUserMessage, messages.put,
                                            errors.put, url,
                                            Headers(self.auth_headers))

        msg1 = self.mkmsg_in(content='in 1', message_id='1')
        yield self.dispatch_with_tag(msg1, self.tag)

        msg2 = self.mkmsg_in(content='in 2', message_id='2')
        yield self.dispatch_with_tag(msg2, self.tag)

        rm1 = yield messages.get()
        rm2 = yield messages.get()

        receiver.disconnect()

        self.assertEqual(msg1['message_id'], rm1['message_id'])
        self.assertEqual(msg2['message_id'], rm2['message_id'])
        self.assertEqual(errors.size, None)

    @inlineCallbacks
    def test_events_stream(self):
        url = '%s/%s/events.json' % (self.url, self.conversation.key)

        events = DeferredQueue()
        errors = DeferredQueue()
        receiver = yield self.client.stream(TransportEvent, events.put,
                                            events.put, url,
                                            Headers(self.auth_headers))

        msg1 = self.mkmsg_out(content='in 1', message_id='1')
        yield self.vumi_api.mdb.add_outbound_message(msg1,
                                                        batch_id=self.batch_id)
        ack1 = self.mkmsg_ack(user_message_id=msg1['message_id'])
        yield self.dispatch_event(ack1)

        msg2 = self.mkmsg_out(content='in 1', message_id='2')
        yield self.vumi_api.mdb.add_outbound_message(msg2,
                                                        batch_id=self.batch_id)
        ack2 = self.mkmsg_ack(user_message_id=msg2['message_id'])
        yield self.dispatch_event(ack2)

        ra1 = yield events.get()
        ra2 = yield events.get()

        receiver.disconnect()

        self.assertEqual(ack1['event_id'], ra1['event_id'])
        self.assertEqual(ack2['event_id'], ra2['event_id'])
        self.assertEqual(errors.size, None)

    @inlineCallbacks
    def test_missing_auth(self):
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)

        queue = DeferredQueue()
        receiver = self.client.stream(TransportUserMessage, queue.put,
                                                queue.put, url)
        response = yield receiver.get_response()
        self.assertEqual(response.code, http.UNAUTHORIZED)
        self.assertEqual(response.headers.getRawHeaders('www-authenticate'), [
            'basic realm="Conversation Stream"'])

    @inlineCallbacks
    def test_invalid_auth(self):
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)

        queue = DeferredQueue()

        headers = Headers({
            'Authorization': ['Basic %s' % (base64.b64encode('foo:bar'),)],
            })

        receiver = self.client.stream(TransportUserMessage, queue.put,
                                                queue.put, url,
                                                headers)
        response = yield receiver.get_response()
        self.assertEqual(response.code, http.UNAUTHORIZED)
        self.assertEqual(response.headers.getRawHeaders('www-authenticate'), [
            'basic realm="Conversation Stream"'])

    @inlineCallbacks
    def test_send_to(self):
        msg = {
            'to_addr': '+2345',
            'content': 'foo',
            'message_id': 'evil_id',
        }

        # TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')

        self.assertEqual(response.code, http.OK)
        put_msg = json.loads(response.delivered_body)

        [sent_msg] = self.get_dispatched_messages()
        self.assertEqual(sent_msg['to_addr'], sent_msg['to_addr'])
        self.assertEqual(sent_msg['helper_metadata'], {
            'go': {
                'user_account': self.account.key,
            },
            'tag': {
                'tag': list(self.tag),
            }
        })
        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['to_addr'], msg['to_addr'])
        self.assertEqual(sent_msg['from_addr'], self.tag[1])

    @inlineCallbacks
    def test_invalid_in_reply_to(self):
        msg = {
            'content': 'foo',
            'in_reply_to': '1',  # this doesn't exist
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')
        self.assertEqual(response.code, http.BAD_REQUEST)

    @inlineCallbacks
    def test_in_reply_to(self):
        inbound_msg = self.mkmsg_in(content='in 1', message_id='1')
        yield self.vumi_api.mdb.add_inbound_message(inbound_msg,
                                                        batch_id=self.batch_id)

        msg = {
            'content': 'foo',
            'in_reply_to': inbound_msg['message_id'],
            'message_id': 'evil_id',
            'session_event': 'evil_event',
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')

        put_msg = json.loads(response.delivered_body)
        self.assertEqual(response.code, http.OK)

        [sent_msg] = self.get_dispatched_messages()
        self.assertEqual(sent_msg['to_addr'], sent_msg['to_addr'])
        self.assertEqual(sent_msg['helper_metadata'], {
            'go': {
                'user_account': self.account.key,
            },
            'tag': {
                'tag': list(self.tag),
            }
        })
        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
        self.assertNotEqual(sent_msg['session_event'], msg['session_event'])
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['to_addr'], inbound_msg['from_addr'])
        self.assertEqual(sent_msg['from_addr'], self.tag[1])

    @inlineCallbacks
    def test_metric_publishing(self):

        metric_data = [
            ("vumi.test.v1", 1234, 'SUM'),
            ("vumi.test.v2", 3456, 'AVG'),
            ]

        url = '%s/%s/metrics.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(metric_data),
                                            self.auth_headers, method='PUT')

        self.assertEqual(response.code, http.OK)

        [metric1, metric2] = self.app.metrics._metrics
        self.assertEqual(metric1.name, '%s%s.%s.vumi.test.v1' % (
            self.config['metrics_prefix'], self.account.key,
            'metrics_store'))
        self.assertEqual(metric1.aggs, ('sum',))

    @inlineCallbacks
    def test_concurrency_limits(self):
        concurrency = ConversationResource.CONCURRENCY_LIMIT
        queue = DeferredQueue()
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        max_receivers = [self.client.stream(TransportUserMessage, queue.put,
                                            queue.put, url,
                                            Headers(self.auth_headers))
                            for _ in range(concurrency)]

        for i in range(concurrency):
            msg = self.mkmsg_in(content='in %s' % (i,), message_id='%s' % (i,))
            yield self.dispatch_with_tag(msg, self.tag)
            received = yield queue.get()
            self.assertEqual(msg['message_id'], received['message_id'])

        maxed_out_resp = yield http_request_full(url, method='GET',
                                                headers=self.auth_headers)

        self.assertEqual(maxed_out_resp.code, 403)
        self.assertTrue('Too many concurrent connections'
                            in maxed_out_resp.delivered_body)

        [r.disconnect() for r in max_receivers]

    @inlineCallbacks
    def test_backlog_on_connect(self):
        for i in range(10):
            msg = self.mkmsg_in(content='in %s' % (i,), message_id=str(i))
            yield self.dispatch_with_tag(msg, self.tag)

        queue = DeferredQueue()
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        receiver = self.client.stream(TransportUserMessage, queue.put,
            queue.put, url, Headers(self.auth_headers))

        for i in range(10):
            received = yield queue.get()
            self.assertEqual(received['message_id'], str(i))

        receiver.disconnect()

    @inlineCallbacks
    def test_health_response(self):
        health_url = 'http://%s:%s%s' % (self.addr.host, self.addr.port,
            self.config['health_path'])

        response = yield http_request_full(health_url, method='GET')
        self.assertEqual(response.delivered_body, '0')

        msg = self.mkmsg_in(content='in 1', message_id='1')
        yield self.dispatch_with_tag(msg, self.tag)

        queue = DeferredQueue()
        stream_url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        stream_receiver = self.client.stream(TransportUserMessage, queue.put,
            queue.put, stream_url, Headers(self.auth_headers))

        yield queue.get()

        response = yield http_request_full(health_url, method='GET')
        self.assertEqual(response.delivered_body, '1')

        stream_receiver.disconnect()

        response = yield http_request_full(health_url, method='GET')
        self.assertEqual(response.delivered_body, '0')
