import base64
import json

from twisted.internet.defer import inlineCallbacks, DeferredQueue, returnValue
from twisted.internet.error import DNSLookupError
from twisted.web.error import SchemeNotSupported
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

from vumi.utils import http_request_full, HttpTimeoutError
from vumi.message import TransportUserMessage, TransportEvent
from vumi.tests.utils import MockHttpServer, LogCatcher

from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.http_api_nostream.vumi_app import NoStreamingHTTPWorker
from go.apps.http_api_nostream.resource import ConversationResource
from go.vumitools.tests.helpers import GoMessageHelper


class NoStreamingHTTPWorkerTestCase(AppWorkerTestCase):
    application_class = NoStreamingHTTPWorker

    @inlineCallbacks
    def setUp(self):
        yield super(NoStreamingHTTPWorkerTestCase, self).setUp()
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

        # Mock server to test HTTP posting of inbound messages & events
        self.mock_push_server = MockHttpServer(self.handle_request)
        yield self.mock_push_server.start()
        self.push_calls = DeferredQueue()
        self._setup_wait_for_request()

        conv_config = {
            'http_api_nostream': {
                'api_tokens': [
                    'token-1',
                    'token-2',
                    'token-3',
                ],
                'push_message_url': self.mock_push_server.url,
                'push_event_url': self.mock_push_server.url,
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

        self.msg_helper = self.add_helper(
            GoMessageHelper(self.user_api.api.mdb))

    @inlineCallbacks
    def tearDown(self):
        yield self._wait_for_requests()
        yield self.mock_push_server.stop()
        yield super(NoStreamingHTTPWorkerTestCase, self).tearDown()

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

    def assert_bad_request(self, response, reason):
        self.assertEqual(response.code, http.BAD_REQUEST)
        data = json.loads(response.delivered_body)
        self.assertEqual(data, {
            "success": False,
            "reason": reason,
        })

    @inlineCallbacks
    def test_missing_auth(self):
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        msg = {
            'to_addr': '+2345',
            'content': 'foo',
            'message_id': 'evil_id',
        }
        response = yield http_request_full(url, json.dumps(msg), {},
                                           method='PUT')
        self.assertEqual(response.code, http.UNAUTHORIZED)
        self.assertEqual(response.headers.getRawHeaders('www-authenticate'), [
            'basic realm="Conversation Realm"'])

    @inlineCallbacks
    def test_invalid_auth(self):
        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        msg = {
            'to_addr': '+2345',
            'content': 'foo',
            'message_id': 'evil_id',
        }
        auth_headers = {
            'Authorization': ['Basic %s' % (base64.b64encode('foo:bar'),)],
        }
        response = yield http_request_full(url, json.dumps(msg), auth_headers,
                                           method='PUT')
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
        self.assertEqual(sent_msg['helper_metadata'], {'go': {
            'conversation_key': self.conversation.key,
            'conversation_type': 'http_api_nostream',
            'user_account': self.account.key,
            'batch_keys': {'conversation': {
                self.conversation.key: self.conversation.batch.key,
            }},
        }})
        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['to_addr'], msg['to_addr'])
        self.assertEqual(sent_msg['from_addr'], None)

    @inlineCallbacks
    def test_in_send_to_with_evil_content(self):
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
    def test_in_send_to_with_evil_to_addr(self):
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
        inbound_msg = yield self.msg_helper.make_stored_inbound(
            self.conversation, 'in 1', message_id='1')

        msg = {
            'content': 'foo',
            'in_reply_to': inbound_msg['message_id'],
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')

        print repr(response.delivered_body)
        put_msg = json.loads(response.delivered_body)
        self.assertEqual(response.code, http.OK)

        [sent_msg] = self.get_dispatched_messages()
        self.assertEqual(sent_msg['to_addr'], put_msg['to_addr'])
        self.assertEqual(sent_msg['helper_metadata'], {'go': {
            'conversation_key': self.conversation.key,
            'conversation_type': 'http_api_nostream',
            'user_account': self.account.key,
            'batch_keys': {'conversation': {
                self.conversation.key: self.conversation.batch.key,
            }},
        }})
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['session_event'], None)
        self.assertEqual(sent_msg['to_addr'], inbound_msg['from_addr'])
        self.assertEqual(sent_msg['from_addr'], '9292')

    @inlineCallbacks
    def test_in_reply_to_with_evil_content(self):
        inbound_msg = yield self.msg_helper.make_stored_inbound(
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

        self.assert_bad_request(response, "Invalid in_reply_to value")
        self.assertTrue(inbound_msg['message_id'] in error_log)

    @inlineCallbacks
    def test_in_reply_to_with_evil_session_event(self):
        inbound_msg = yield self.msg_helper.make_stored_inbound(
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
        self.assertEqual(self.get_dispatched_messages(), [])

    @inlineCallbacks
    def test_in_reply_to_with_evil_message_id(self):
        inbound_msg = yield self.msg_helper.make_stored_inbound(
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
        put_msg = json.loads(response.delivered_body)
        [sent_msg] = self.get_dispatched_messages()

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

        prefix = "campaigns.test-0-user.stores.metrics_store"

        self.assertEqual(
            self.get_published_metrics(self.app),
            [("%s.vumi.test.v1" % prefix, 1234),
             ("%s.vumi.test.v2" % prefix, 3456)])

    @inlineCallbacks
    def receive_pushed_message(self, publish_d=None):
        req = yield self.push_calls.get()
        received = req.content.read()
        self.assertEqual(
            req.requestHeaders.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        req.finish()
        yield publish_d
        returnValue(json.loads(received))

    @inlineCallbacks
    def test_health_response(self):
        health_url = 'http://%s:%s%s' % (
            self.addr.host, self.addr.port, self.config['health_path'])

        response = yield http_request_full(health_url, method='GET')
        self.assertEqual(response.delivered_body, 'OK')

    @inlineCallbacks
    def test_post_inbound_message(self):
        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        posted_json = yield self.receive_pushed_message(
            self.dispatch_to_conv(msg, self.conversation))

        posted_msg = TransportUserMessage.from_json(json.dumps(posted_json))
        self.assertEqual(posted_msg['message_id'], msg['message_id'])

    def _patch_http_request_full(self, exception_class):
        from go.apps.http_api_nostream import vumi_app

        def raiser(*args, **kw):
            raise exception_class()
        self.patch(vumi_app, 'http_request_full', raiser)

    @inlineCallbacks
    def test_post_inbound_message_no_url(self):
        self.conversation.config['http_api_nostream'].update({
            'push_message_url': None,
        })
        yield self.conversation.save()

        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        with LogCatcher(message='push_message_url not configured') as lc:
            yield self.dispatch_to_conv(msg, self.conversation)
            [url_not_configured_log] = lc.messages()
        self.assertTrue(self.conversation.key in url_not_configured_log)

    @inlineCallbacks
    def test_post_inbound_message_unsupported_scheme(self):
        self.conversation.config['http_api_nostream'].update({
            'push_message_url': 'example.com',
        })
        yield self.conversation.save()

        self._patch_http_request_full(SchemeNotSupported)
        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        with LogCatcher(message='Unsupported') as lc:
            yield self.dispatch_to_conv(msg, self.conversation)
            [unsupported_scheme_log] = lc.messages()
        self.assertTrue('example.com' in unsupported_scheme_log)

    @inlineCallbacks
    def test_post_inbound_message_timeout(self):
        self._patch_http_request_full(HttpTimeoutError)
        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        with LogCatcher(message='Timeout') as lc:
            yield self.dispatch_to_conv(msg, self.conversation)
            [timeout_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in timeout_log)

    @inlineCallbacks
    def test_post_inbound_message_dns_lookup_error(self):
        self._patch_http_request_full(DNSLookupError)
        msg = self.msg_helper.make_inbound('in 1', message_id='1')
        with LogCatcher(message='DNS lookup error') as lc:
            yield self.dispatch_to_conv(msg, self.conversation)
            [dns_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in dns_log)

    @inlineCallbacks
    def test_post_inbound_event(self):
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
    def test_post_inbound_event_no_url(self):
        self.conversation.config['http_api_nostream'].update({
            'push_event_url': None,
        })
        yield self.conversation.save()

        msg1 = yield self.msg_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        ack1 = self.msg_helper.make_ack(msg1)
        with LogCatcher(message='push_event_url not configured') as lc:
            yield self.dispatch_event_to_conv(ack1, self.conversation)
            [url_not_configured_log] = lc.messages()
        self.assertTrue(self.conversation.key in url_not_configured_log)

    @inlineCallbacks
    def test_post_inbound_event_timeout(self):
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
