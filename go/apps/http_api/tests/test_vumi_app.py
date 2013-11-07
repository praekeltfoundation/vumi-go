import base64
import json

from twisted.internet.defer import inlineCallbacks, DeferredQueue, returnValue
from twisted.internet.error import DNSLookupError
from twisted.web.http_headers import Headers
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

from vumi.utils import http_request_full, HttpTimeoutError
from vumi.message import TransportUserMessage, TransportEvent
from vumi.tests.utils import MockHttpServer, LogCatcher
from vumi.transports.vumi_bridge.client import StreamingClient
from vumi.config import ConfigContext

from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.http_api.vumi_app import StreamingHTTPWorker
from go.apps.http_api.resource import StreamResource, ConversationResource
from go.vumitools.tests.helpers import GoMessageHelper


class StreamingHTTPWorkerTestCase(AppWorkerTestCase):
    application_class = StreamingHTTPWorker

    @inlineCallbacks
    def setUp(self):
        yield super(StreamingHTTPWorkerTestCase, self).setUp()
        self.config = self.mk_config({
            'health_path': '/health/',
            'web_path': '/foo',
            'web_port': 0,
            'metrics_prefix': 'metrics_prefix.',
        })
        self.app = yield self.get_application(self.config)
        self.addr = self.app.webserver.getHost()
        self.url = 'http://%s:%s%s' % (
            self.addr.host, self.addr.port, self.config['web_path'])

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!

        # Create a test user account
        self.account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.account.key)

        yield self.setup_tagpools()

        conv_config = {
            'http_api': {
                'api_tokens': [
                    'token-1',
                    'token-2',
                    'token-3',
                ],
                'metrics_store': 'metrics_store',
            }
        }
        conversation = yield self.create_conversation(config=conv_config)
        yield self.start_conversation(conversation)
        self.conversation = yield self.user_api.get_wrapped_conversation(
            conversation.key)

        self.auth_headers = {
            'Authorization': ['Basic ' + base64.b64encode('%s:%s' % (
                self.account.key, 'token-1'))],
        }

        self.client = StreamingClient()

        # Mock server to test HTTP posting of inbound messages & events
        self.mock_push_server = MockHttpServer(self.handle_request)
        yield self.mock_push_server.start()
        self.push_calls = DeferredQueue()
        self._setup_wait_for_request()
        self.msg_helper = GoMessageHelper(self.user_api.api.mdb)

    @inlineCallbacks
    def tearDown(self):
        yield self._wait_for_requests()
        yield self.mock_push_server.stop()
        yield super(StreamingHTTPWorkerTestCase, self).tearDown()

    def _setup_wait_for_request(self):
        # Hackery to wait for the request to finish
        self._req_state = {
            'queue': DeferredQueue(),
            'expected': 0,
        }
        orig_track = ConversationResource.track_request
        orig_release = ConversationResource.release_request

        def track_wrapper(*args, **kw):
            self._req_state['expected'] += 1
            return orig_track(*args, **kw)

        def release_wrapper(*args, **kw):
            return orig_release(*args, **kw).addCallback(
                self._req_state['queue'].put)

        self.patch(ConversationResource, 'track_request', track_wrapper)
        self.patch(ConversationResource, 'release_request', release_wrapper)

    @inlineCallbacks
    def _wait_for_requests(self):
        while self._req_state['expected'] > 0:
            yield self._req_state['queue'].get()
            self._req_state['expected'] -= 1

    def handle_request(self, request):
        self.push_calls.put(request)
        return NOT_DONE_YET

    @inlineCallbacks
    def pull_message(self, count=1):
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)

        messages = DeferredQueue()
        errors = DeferredQueue()
        receiver = self.client.stream(
            TransportUserMessage, messages.put, errors.put, url,
            Headers(self.auth_headers))

        received_messages = []
        for msg_id in range(count):
            sent_msg = self.msg_helper.make_inbound(
                'in %s' % (msg_id,), message_id=str(msg_id))
            yield self.dispatch_to_conv(sent_msg, self.conversation)
            recv_msg = yield messages.get()
            received_messages.append(recv_msg)

        receiver.disconnect()
        returnValue((receiver, received_messages))

    @inlineCallbacks
    def test_proxy_buffering_headers_off(self):
        receiver, received_messages = yield self.pull_message()
        headers = receiver._response.headers
        self.assertEqual(headers.getRawHeaders('x-accel-buffering'), ['no'])

    @inlineCallbacks
    def test_proxy_buffering_headers_on(self):
        StreamResource.proxy_buffering = True
        receiver, received_messages = yield self.pull_message()
        headers = receiver._response.headers
        self.assertEqual(headers.getRawHeaders('x-accel-buffering'), ['yes'])

    @inlineCallbacks
    def test_content_type(self):
        receiver, received_messages = yield self.pull_message()
        headers = receiver._response.headers
        self.assertEqual(
            headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])

    @inlineCallbacks
    def test_messages_stream(self):
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)

        messages = DeferredQueue()
        errors = DeferredQueue()
        receiver = self.client.stream(
            TransportUserMessage, messages.put, errors.put, url,
            Headers(self.auth_headers))

        msg1 = self.msg_helper.make_inbound('in 1', message_id='1')
        yield self.dispatch_to_conv(msg1, self.conversation)

        msg2 = self.msg_helper.make_inbound('in 2', message_id='2')
        yield self.dispatch_to_conv(msg2, self.conversation)

        rm1 = yield messages.get()
        rm2 = yield messages.get()

        receiver.disconnect()

        # Sometimes messages arrive out of order if we're hitting real redis.
        rm1, rm2 = sorted([rm1, rm2], key=lambda m: m['message_id'])

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

        msg1 = yield self.msg_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        ack1 = self.msg_helper.make_ack(msg1)
        yield self.dispatch_event_to_conv(ack1, self.conversation)

        msg2 = yield self.msg_helper.make_stored_outbound(
            self.conversation, 'out 2', message_id='2')
        ack2 = self.msg_helper.make_ack(msg2)
        yield self.dispatch_event_to_conv(ack2, self.conversation)

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
        receiver = self.client.stream(
            TransportUserMessage, queue.put, queue.put, url)
        response = yield receiver.get_response()
        self.assertEqual(response.code, http.UNAUTHORIZED)
        self.assertEqual(response.headers.getRawHeaders('www-authenticate'), [
            'basic realm="Conversation Realm"'])

    @inlineCallbacks
    def test_invalid_auth(self):
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)

        queue = DeferredQueue()

        headers = Headers({
            'Authorization': ['Basic %s' % (base64.b64encode('foo:bar'),)],
        })

        receiver = self.client.stream(
            TransportUserMessage, queue.put, queue.put, url, headers)
        response = yield receiver.get_response()
        self.assertEqual(response.code, http.UNAUTHORIZED)
        self.assertEqual(response.headers.getRawHeaders('www-authenticate'), [
            'basic realm="Conversation Realm"'])

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
                'conversation_key': self.conversation.key,
                'conversation_type': 'http_api',
                'user_account': self.account.key,
            },
        })
        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['to_addr'], msg['to_addr'])
        self.assertEqual(sent_msg['from_addr'], None)

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
    def test_invalid_in_reply_to_with_missing_conversation_key(self):
        # create a message with no (None) conversation
        inbound_msg = self.msg_helper.make_inbound('in 1', message_id='msg-1')
        yield self.msg_helper.mdb.add_inbound_message(inbound_msg)

        msg = {
            'content': 'foo',
            'in_reply_to': inbound_msg['message_id'],
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        with LogCatcher(message='Invalid reply to message <Message .*>'
                        ' which has no conversation key') as lc:
            response = yield http_request_full(url, json.dumps(msg),
                                               self.auth_headers, method='PUT')
            [error_log] = lc.messages()

        self.assertEqual(response.code, http.BAD_REQUEST)
        self.assertTrue(inbound_msg['message_id'] in error_log)

    @inlineCallbacks
    def test_in_reply_to(self):
        inbound_msg = yield self.msg_helper.make_stored_inbound(
            self.conversation, 'in 1', message_id='1')

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
                'conversation_key': self.conversation.key,
                'conversation_type': 'http_api',
                'user_account': self.account.key,
            },
        })
        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
        self.assertNotEqual(sent_msg['session_event'], msg['session_event'])
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['to_addr'], inbound_msg['from_addr'])
        self.assertEqual(sent_msg['from_addr'], '9292')

    @inlineCallbacks
    def test_metric_publishing(self):

        metric_data = [
            ("vumi.test.v1", 1234, 'SUM'),
            ("vumi.test.v2", 3456, 'AVG'),
        ]

        url = '%s/%s/metrics.json' % (self.url, self.conversation.key)
        response = yield http_request_full(
            url, json.dumps(metric_data), self.auth_headers, method='PUT')

        self.assertEqual(response.code, http.OK)

        prefix = "campaigns.test-0-user.stores.metrics_store"

        self.assertEqual(
            self.get_published_metrics(self.app),
            [("%s.vumi.test.v1" % prefix, 1234),
             ("%s.vumi.test.v2" % prefix, 3456)])

    @inlineCallbacks
    def test_concurrency_limits(self):
        config = yield self.app.get_config(None)
        concurrency = config.concurrency_limit
        queue = DeferredQueue()
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        max_receivers = [self.client.stream(
            TransportUserMessage, queue.put, queue.put, url,
            Headers(self.auth_headers)) for _ in range(concurrency)]

        for i in range(concurrency):
            msg = self.msg_helper.make_inbound(
                'in %s' % (i,), message_id=str(i))
            yield self.dispatch_to_conv(msg, self.conversation)
            received = yield queue.get()
            self.assertEqual(msg['message_id'], received['message_id'])

        maxed_out_resp = yield http_request_full(
            url, method='GET', headers=self.auth_headers)

        self.assertEqual(maxed_out_resp.code, 403)
        self.assertTrue(
            'Too many concurrent connections' in maxed_out_resp.delivered_body)

        [r.disconnect() for r in max_receivers]

    @inlineCallbacks
    def test_disabling_concurrency_limit(self):
        conv_resource = ConversationResource(self.app, self.conversation.key)
        # negative concurrency limit disables it
        ctxt = ConfigContext(user_account=self.account.key,
                             concurrency_limit=-1)
        config = yield self.app.get_config(msg=None, ctxt=ctxt)
        self.assertTrue(
            (yield conv_resource.is_allowed(config, self.account.key)))

    @inlineCallbacks
    def test_backlog_on_connect(self):
        for i in range(10):
            msg = self.msg_helper.make_inbound(
                'in %s' % (i,), message_id=str(i))
            yield self.dispatch_to_conv(msg, self.conversation)

        queue = DeferredQueue()
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        receiver = self.client.stream(
            TransportUserMessage, queue.put, queue.put, url,
            Headers(self.auth_headers))

        for i in range(10):
            received = yield queue.get()
            self.assertEqual(received['message_id'], str(i))

        receiver.disconnect()

    @inlineCallbacks
    def test_health_response(self):
        health_url = 'http://%s:%s%s' % (
            self.addr.host, self.addr.port, self.config['health_path'])

        response = yield http_request_full(health_url, method='GET')
        self.assertEqual(response.delivered_body, '0')

        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        yield self.dispatch_to_conv(msg, self.conversation)

        queue = DeferredQueue()
        stream_url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        stream_receiver = self.client.stream(
            TransportUserMessage, queue.put, queue.put, stream_url,
            Headers(self.auth_headers))

        yield queue.get()

        response = yield http_request_full(health_url, method='GET')
        self.assertEqual(response.delivered_body, '1')

        stream_receiver.disconnect()

        response = yield http_request_full(health_url, method='GET')
        self.assertEqual(response.delivered_body, '0')

        self.assertEqual(self.app.client_manager.clients, {
            'sphex.stream.message.%s' % (self.conversation.key,): []
        })

    @inlineCallbacks
    def test_post_inbound_message(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_message_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        msg_d = self.dispatch_to_conv(msg, self.conversation)

        req = yield self.push_calls.get()
        posted_json_data = req.content.read()
        req.finish()
        yield msg_d

        posted_msg = TransportUserMessage.from_json(posted_json_data)
        self.assertEqual(posted_msg['message_id'], msg['message_id'])

    def _patch_http_request_full(self, exception_class):
        from go.apps.http_api import vumi_app

        def raiser(*args, **kw):
            raise exception_class()
        self.patch(vumi_app, 'http_request_full', raiser)

    @inlineCallbacks
    def test_post_inbound_message_timeout(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_message_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        self._patch_http_request_full(HttpTimeoutError)
        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        with LogCatcher(message='Timeout') as lc:
            yield self.dispatch_to_conv(msg, self.conversation)
            [timeout_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in timeout_log)

    @inlineCallbacks
    def test_post_inbound_message_dns_lookup_error(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_message_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        self._patch_http_request_full(DNSLookupError)
        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        with LogCatcher(message='DNS lookup error') as lc:
            yield self.dispatch_to_conv(msg, self.conversation)
            [dns_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in dns_log)

    @inlineCallbacks
    def test_post_inbound_event(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_event_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        msg1 = yield self.msg_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        ack1 = self.msg_helper.make_ack(msg1)
        event_d = self.dispatch_event_to_conv(ack1, self.conversation)

        req = yield self.push_calls.get()
        posted_json_data = req.content.read()
        req.finish()
        yield event_d

        self.assertEqual(TransportEvent.from_json(posted_json_data), ack1)

    @inlineCallbacks
    def test_post_inbound_event_timeout(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_event_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        msg1 = yield self.msg_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        ack1 = self.msg_helper.make_ack(msg1)

        self._patch_http_request_full(HttpTimeoutError)
        with LogCatcher(message='Timeout') as lc:
            yield self.dispatch_event_to_conv(ack1, self.conversation)
            [timeout_log] = lc.messages()
        self.assertTrue(timeout_log.endswith(self.mock_push_server.url))

    @inlineCallbacks
    def test_post_inbound_event_dns_lookup_error(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_event_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        msg1 = yield self.msg_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        ack1 = self.msg_helper.make_ack(msg1)

        self._patch_http_request_full(DNSLookupError)
        with LogCatcher(message='DNS lookup error') as lc:
            yield self.dispatch_event_to_conv(ack1, self.conversation)
            [dns_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in dns_log)

    @inlineCallbacks
    def test_bad_urls(self):
        def assert_not_found(url, headers={}):
            d = http_request_full(self.url, method='GET', headers=headers)
            d.addCallback(lambda r: self.assertEqual(r.code, http.NOT_FOUND))
            return d

        yield assert_not_found(self.url)
        yield assert_not_found(self.url + '/')
        yield assert_not_found('%s/%s' % (self.url, self.conversation.key),
                               headers=self.auth_headers)
        yield assert_not_found('%s/%s/' % (self.url, self.conversation.key),
                               headers=self.auth_headers)
        yield assert_not_found('%s/%s/foo' % (self.url, self.conversation.key),
                               headers=self.auth_headers)

    @inlineCallbacks
    def test_send_message_command(self):
        yield self.dispatch_command(
            'send_message',
            user_account_key=self.account.key,
            conversation_key=self.conversation.key,
            command_data={
                u'batch_id': u'batch-id',
                u'content': u'foo',
                u'to_addr': u'to_addr',
                u'msg_options': {
                    u'helper_metadata': {
                        u'tag': {
                            u'tag': [u'longcode', u'default10080']
                        }
                    },
                    u'transport_name': self.transport_name,
                    u'transport_type': self.transport_type,
                    u'from_addr': u'default10080',
                }
            })

        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg.payload['to_addr'], "to_addr")
        self.assertEqual(msg.payload['from_addr'], "default10080")
        self.assertEqual(msg.payload['content'], "foo")
        self.assertEqual(msg.payload['transport_name'], self.transport_name)
        self.assertEqual(msg.payload['transport_type'], self.transport_type)
        self.assertEqual(msg.payload['message_type'], "user_message")
        self.assertEqual(
            msg.payload['helper_metadata']['go']['user_account'],
            self.account.key)
        self.assertEqual(
            msg.payload['helper_metadata']['tag']['tag'],
            ['longcode', 'default10080'])

    @inlineCallbacks
    def test_process_command_send_message_in_reply_to(self):
        msg = yield self.msg_helper.make_stored_inbound(
            self.conversation, "foo")
        yield self.dispatch_command(
            'send_message',
            user_account_key=self.account.key,
            conversation_key=self.conversation.key,
            command_data={
                u'batch_id': u'batch-id',
                u'content': u'foo',
                u'to_addr': u'to_addr',
                u'msg_options': {
                    u'helper_metadata': {
                        u'tag': {
                            u'tag': [u'longcode', u'default10080']
                        }
                    },
                    u'transport_name': u'smpp_transport',
                    u'in_reply_to': msg['message_id'],
                    u'transport_type': u'sms',
                    u'from_addr': u'default10080',
                }
            })
        [sent_msg] = self.get_dispatched_messages()
        self.assertEqual(sent_msg['to_addr'], msg['from_addr'])
        self.assertEqual(sent_msg['content'], 'foo')
        self.assertEqual(sent_msg['in_reply_to'], msg['message_id'])
