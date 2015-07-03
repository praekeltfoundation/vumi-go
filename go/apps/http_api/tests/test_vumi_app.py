import base64
import json

from twisted.internet.defer import inlineCallbacks, DeferredQueue, returnValue
from twisted.web.http_headers import Headers
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

from vumi.config import ConfigContext
from vumi.message import TransportUserMessage, TransportEvent
from vumi.tests.helpers import VumiTestCase
from vumi.tests.utils import MockHttpServer, LogCatcher
from vumi.transports.vumi_bridge.client import StreamingClient
from vumi.utils import http_request_full

from go.apps.http_api.resource import (
    StreamResourceMixin, StreamingConversationResource)
from go.apps.http_api.vumi_app import StreamingHTTPWorker
from go.apps.tests.helpers import AppWorkerHelper


class TestStreamingHTTPWorker(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(AppWorkerHelper(StreamingHTTPWorker))

        self.config = {
            'health_path': '/health/',
            'web_path': '/foo',
            'web_port': 0,
            'metrics_prefix': 'metrics_prefix.',
            'conversation_cache_ttl': 0,
        }
        self.app = yield self.app_helper.get_app_worker(self.config)
        self.addr = self.app.webserver.getHost()
        self.url = 'http://%s:%s%s' % (
            self.addr.host, self.addr.port, self.config['web_path'])

        conv_config = {
            'http_api': {
                'api_tokens': [
                    'token-1',
                    'token-2',
                    'token-3',
                ],
                'metric_store': 'metric_store',
            }
        }
        conversation = yield self.app_helper.create_conversation(
            config=conv_config)
        yield self.app_helper.start_conversation(conversation)
        self.conversation = yield self.app_helper.get_conversation(
            conversation.key)

        self.auth_headers = {
            'Authorization': ['Basic ' + base64.b64encode('%s:%s' % (
                conversation.user_account.key, 'token-1'))],
        }

        self.client = StreamingClient()

        # Mock server to test HTTP posting of inbound messages & events
        self.mock_push_server = MockHttpServer(self.handle_request)
        yield self.mock_push_server.start()
        self.add_cleanup(self.mock_push_server.stop)
        self.push_calls = DeferredQueue()
        self._setup_wait_for_request()
        self.add_cleanup(self._wait_for_requests)

    def _setup_wait_for_request(self):
        # Hackery to wait for the request to finish
        self._req_state = {
            'queue': DeferredQueue(),
            'expected': 0,
        }
        orig_track = StreamingConversationResource.track_request
        orig_release = StreamingConversationResource.release_request

        def track_wrapper(*args, **kw):
            self._req_state['expected'] += 1
            return orig_track(*args, **kw)

        def release_wrapper(*args, **kw):
            return orig_release(*args, **kw).addCallback(
                self._req_state['queue'].put)

        self.patch(
            StreamingConversationResource, 'track_request', track_wrapper)
        self.patch(
            StreamingConversationResource, 'release_request', release_wrapper)

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
            yield self.app_helper.make_dispatch_inbound(
                'in %s' % (msg_id,), message_id=str(msg_id),
                conv=self.conversation)
            recv_msg = yield messages.get()
            received_messages.append(recv_msg)

        receiver.disconnect()
        returnValue((receiver, received_messages))

    def assert_bad_request(self, response, reason):
        self.assertEqual(response.code, http.BAD_REQUEST)
        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        data = json.loads(response.delivered_body)
        self.assertEqual(data, {
            "success": False,
            "reason": reason,
        })

    @inlineCallbacks
    def test_proxy_buffering_headers_off(self):
        # This is the default, but we patch it anyway to make sure we're
        # testing the right thing should the default change.
        self.patch(StreamResourceMixin, 'proxy_buffering', False)
        receiver, received_messages = yield self.pull_message()
        headers = receiver._response.headers
        self.assertEqual(headers.getRawHeaders('x-accel-buffering'), ['no'])

    @inlineCallbacks
    def test_proxy_buffering_headers_on(self):
        self.patch(StreamResourceMixin, 'proxy_buffering', True)
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

        msg1 = yield self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)

        msg2 = yield self.app_helper.make_dispatch_inbound(
            'in 2', message_id='2', conv=self.conversation)

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

        msg1 = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        ack1 = yield self.app_helper.make_dispatch_ack(
            msg1, conv=self.conversation)

        msg2 = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 2', message_id='2')
        ack2 = yield self.app_helper.make_dispatch_ack(
            msg2, conv=self.conversation)

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

        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        self.assertEqual(response.code, http.OK)
        put_msg = json.loads(response.delivered_body)

        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], sent_msg['to_addr'])
        self.assertEqual(sent_msg['helper_metadata'], {
            'go': {
                'conversation_key': self.conversation.key,
                'conversation_type': 'http_api',
                'user_account': self.conversation.user_account.key,
            },
        })
        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['to_addr'], msg['to_addr'])
        self.assertEqual(sent_msg['from_addr'], None)

    @inlineCallbacks
    def test_send_to_within_content_length_limit(self):
        self.conversation.config['http_api'].update({
            'content_length_limit': 182,
        })
        yield self.conversation.save()

        msg = {
            'content': 'foo',
            'to_addr': '+1234',
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')
        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        put_msg = json.loads(response.delivered_body)
        self.assertEqual(response.code, http.OK)

        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], put_msg['to_addr'])
        self.assertEqual(sent_msg['helper_metadata'], {
            'go': {
                'conversation_key': self.conversation.key,
                'conversation_type': 'http_api',
                'user_account': self.conversation.user_account.key,
            },
        })
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['session_event'], None)
        self.assertEqual(sent_msg['to_addr'], '+1234')
        self.assertEqual(sent_msg['from_addr'], None)

    @inlineCallbacks
    def test_send_to_content_too_long(self):
        self.conversation.config['http_api'].update({
            'content_length_limit': 10,
        })
        yield self.conversation.save()

        msg = {
            'content': "This message is longer than 10 characters.",
            'to_addr': '+1234',
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(
            url, json.dumps(msg), self.auth_headers, method='PUT')
        self.assert_bad_request(
            response, "Payload content too long: 42 > 10")

    @inlineCallbacks
    def test_send_to_with_evil_content(self):
        msg = {
            'content': 0xBAD,
            'to_addr': '+1234',
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')
        self.assert_bad_request(
            response, "Invalid or missing value for payload key 'content'")

    @inlineCallbacks
    def test_send_to_with_evil_to_addr(self):
        msg = {
            'content': 'good',
            'to_addr': 1234,
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')
        self.assert_bad_request(
            response, "Invalid or missing value for payload key 'to_addr'")

    @inlineCallbacks
    def test_in_reply_to(self):
        inbound_msg = yield self.app_helper.make_stored_inbound(
            self.conversation, 'in 1', message_id='1')

        msg = {
            'content': 'foo',
            'in_reply_to': inbound_msg['message_id'],
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')

        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        put_msg = json.loads(response.delivered_body)
        self.assertEqual(response.code, http.OK)

        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], put_msg['to_addr'])
        self.assertEqual(sent_msg['helper_metadata'], {
            'go': {
                'conversation_key': self.conversation.key,
                'conversation_type': 'http_api',
                'user_account': self.conversation.user_account.key,
            },
        })
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['session_event'], None)
        self.assertEqual(sent_msg['to_addr'], inbound_msg['from_addr'])
        self.assertEqual(sent_msg['from_addr'], '9292')

    @inlineCallbacks
    def test_in_reply_to_within_content_length_limit(self):
        self.conversation.config['http_api'].update({
            'content_length_limit': 182,
        })
        yield self.conversation.save()

        inbound_msg = yield self.app_helper.make_stored_inbound(
            self.conversation, 'in 1', message_id='1')

        msg = {
            'content': 'foo',
            'in_reply_to': inbound_msg['message_id'],
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')
        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        put_msg = json.loads(response.delivered_body)
        self.assertEqual(response.code, http.OK)

        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], put_msg['to_addr'])
        self.assertEqual(sent_msg['helper_metadata'], {
            'go': {
                'conversation_key': self.conversation.key,
                'conversation_type': 'http_api',
                'user_account': self.conversation.user_account.key,
            },
        })
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['session_event'], None)
        self.assertEqual(sent_msg['to_addr'], inbound_msg['from_addr'])
        self.assertEqual(sent_msg['from_addr'], '9292')

    @inlineCallbacks
    def test_in_reply_to_content_too_long(self):
        self.conversation.config['http_api'].update({
            'content_length_limit': 10,
        })
        yield self.conversation.save()

        inbound_msg = yield self.app_helper.make_stored_inbound(
            self.conversation, 'in 1', message_id='1')

        msg = {
            'content': "This message is longer than 10 characters.",
            'in_reply_to': inbound_msg['message_id'],
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(
            url, json.dumps(msg), self.auth_headers, method='PUT')
        self.assert_bad_request(
            response, "Payload content too long: 42 > 10")

    @inlineCallbacks
    def test_in_reply_to_with_evil_content(self):
        inbound_msg = yield self.app_helper.make_stored_inbound(
            self.conversation, 'in 1', message_id='1')

        msg = {
            'content': 0xBAD,
            'in_reply_to': inbound_msg['message_id'],
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')
        self.assert_bad_request(
            response, "Invalid or missing value for payload key 'content'")

    @inlineCallbacks
    def test_invalid_in_reply_to(self):
        msg = {
            'content': 'foo',
            'in_reply_to': '1',  # this doesn't exist
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')
        self.assert_bad_request(response, 'Invalid in_reply_to value')

    @inlineCallbacks
    def test_invalid_in_reply_to_with_missing_conversation_key(self):
        # create a message with no conversation
        inbound_msg = self.app_helper.make_inbound('in 1', message_id='msg-1')
        vumi_api = self.app_helper.vumi_helper.get_vumi_api()
        opms = vumi_api.get_operational_message_store()
        yield opms.add_inbound_message(inbound_msg)

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

        self.assert_bad_request(response, "Invalid in_reply_to value")
        self.assertTrue(inbound_msg['message_id'] in error_log)

    @inlineCallbacks
    def test_in_reply_to_with_evil_session_event(self):
        inbound_msg = yield self.app_helper.make_stored_inbound(
            self.conversation, 'in 1', message_id='1')

        msg = {
            'content': 'foo',
            'in_reply_to': inbound_msg['message_id'],
            'session_event': 0xBAD5E55104,
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')

        self.assert_bad_request(
            response,
            "Invalid or missing value for payload key 'session_event'")
        self.assertEqual(self.app_helper.get_dispatched_outbound(), [])

    @inlineCallbacks
    def test_in_reply_to_with_evil_message_id(self):
        inbound_msg = yield self.app_helper.make_stored_inbound(
            self.conversation, 'in 1', message_id='1')

        msg = {
            'content': 'foo',
            'in_reply_to': inbound_msg['message_id'],
            'message_id': 'evil_id'
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')

        self.assertEqual(response.code, http.OK)
        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        put_msg = json.loads(response.delivered_body)
        [sent_msg] = self.app_helper.get_dispatched_outbound()

        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
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
        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])

        prefix = "go.campaigns.test-0-user.stores.metric_store"

        self.assertEqual(
            self.app_helper.get_published_metrics(self.app),
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
            msg = yield self.app_helper.make_dispatch_inbound(
                'in %s' % (i,), message_id=str(i), conv=self.conversation)
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
        conv_resource = StreamingConversationResource(
            self.app, self.conversation.key)
        # negative concurrency limit disables it
        ctxt = ConfigContext(user_account=self.conversation.user_account.key,
                             concurrency_limit=-1)
        config = yield self.app.get_config(msg=None, ctxt=ctxt)
        self.assertTrue(
            (yield conv_resource.is_allowed(
                config, self.conversation.user_account.key)))

    @inlineCallbacks
    def test_backlog_on_connect(self):
        for i in range(10):
            yield self.app_helper.make_dispatch_inbound(
                'in %s' % (i,), message_id=str(i), conv=self.conversation)

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

        yield self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)

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

        msg_d = self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)

        req = yield self.push_calls.get()
        posted_json_data = req.content.read()
        req.finish()
        msg = yield msg_d

        posted_msg = TransportUserMessage.from_json(posted_json_data)
        self.assertEqual(posted_msg['message_id'], msg['message_id'])

    @inlineCallbacks
    def test_post_inbound_message_201_response(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_message_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        with LogCatcher(message='Got unexpected response code') as lc:
            msg_d = self.app_helper.make_dispatch_inbound(
                'in 1', message_id='1', conv=self.conversation)
            req = yield self.push_calls.get()
            req.setResponseCode(201)
            req.finish()
            yield msg_d
        self.assertEqual(lc.messages(), [])

    @inlineCallbacks
    def test_post_inbound_message_500_response(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_message_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        with LogCatcher(message='Got unexpected response code') as lc:
            msg_d = self.app_helper.make_dispatch_inbound(
                'in 1', message_id='1', conv=self.conversation)
            req = yield self.push_calls.get()
            req.setResponseCode(500)
            req.finish()
            yield msg_d
        [warning_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in warning_log)
        self.assertTrue('500' in warning_log)

    @inlineCallbacks
    def test_post_inbound_event(self):
        # Set the URL so stuff is HTTP Posted instead of streamed.
        self.conversation.config['http_api'].update({
            'push_event_url': self.mock_push_server.url,
        })
        yield self.conversation.save()

        msg = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        event_d = self.app_helper.make_dispatch_ack(
            msg, conv=self.conversation)

        req = yield self.push_calls.get()
        posted_json_data = req.content.read()
        req.finish()
        ack = yield event_d

        self.assertEqual(TransportEvent.from_json(posted_json_data), ack)

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
        yield self.app_helper.dispatch_command(
            'send_message',
            user_account_key=self.conversation.user_account.key,
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
                    u'from_addr': u'default10080',
                }
            })

        [msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(msg.payload['to_addr'], "to_addr")
        self.assertEqual(msg.payload['from_addr'], "default10080")
        self.assertEqual(msg.payload['content'], "foo")
        self.assertEqual(msg.payload['message_type'], "user_message")
        self.assertEqual(
            msg.payload['helper_metadata']['go']['user_account'],
            self.conversation.user_account.key)
        self.assertEqual(
            msg.payload['helper_metadata']['tag']['tag'],
            ['longcode', 'default10080'])

    @inlineCallbacks
    def test_process_command_send_message_in_reply_to(self):
        msg = yield self.app_helper.make_stored_inbound(
            self.conversation, "foo")
        yield self.app_helper.dispatch_command(
            'send_message',
            user_account_key=self.conversation.user_account.key,
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
        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], msg['from_addr'])
        self.assertEqual(sent_msg['content'], 'foo')
        self.assertEqual(sent_msg['in_reply_to'], msg['message_id'])
