import base64
import json
import logging
from urlparse import urlparse, urlunparse

from twisted.internet.defer import inlineCallbacks, DeferredQueue, returnValue
from twisted.internet.error import DNSLookupError, ConnectionRefusedError
from twisted.web.error import SchemeNotSupported
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

from vumi.utils import http_request_full, HttpTimeoutError
from vumi.message import TransportUserMessage, TransportEvent
from vumi.tests.utils import MockHttpServer, LogCatcher
from vumi.tests.helpers import VumiTestCase

from go.apps.http_api_nostream.vumi_app import (
    ConcurrencyLimitManager, NoStreamingHTTPWorker)
from go.apps.http_api_nostream.resource import ConversationResource
from go.apps.tests.helpers import AppWorkerHelper


class TestConcurrencyLimitManager(VumiTestCase):
    def test_concurrency_limiter_no_limit(self):
        """
        When given a negitive limit, ConcurrencyLimitManager never blocks.
        """
        limiter = ConcurrencyLimitManager(-1)
        d1 = limiter.start("key")
        self.assertEqual(d1.called, True)
        d2 = limiter.start("key")
        self.assertEqual(d2.called, True)

        # Check that we aren't storing any state.
        self.assertEqual(limiter._concurrency_limiters, {})

        # Check that stopping doesn't explode.
        limiter.stop("key")

    def test_concurrency_limiter_zero_limit(self):
        """
        When given a limit of zero, ConcurrencyLimitManager always blocks
        forever.
        """
        limiter = ConcurrencyLimitManager(0)
        d1 = limiter.start("key")
        self.assertEqual(d1.called, False)
        d2 = limiter.start("key")
        self.assertEqual(d2.called, False)

        # Check that we aren't storing any state.
        self.assertEqual(limiter._concurrency_limiters, {})

        # Check that stopping doesn't explode.
        limiter.stop("key")

    def test_concurrency_limiter_stop_without_start(self):
        """
        ConcurrencyLimitManager raises an exception if stop() is called without
        a prior call to start().
        """
        limiter = ConcurrencyLimitManager(1)
        self.assertRaises(Exception, limiter.stop)

    def test_concurrency_limiter_one_limit(self):
        """
        ConcurrencyLimitManager fires the next deferred in the queue when
        stop() is called.
        """
        limiter = ConcurrencyLimitManager(1)
        d1 = limiter.start("key")
        self.assertEqual(d1.called, True)
        d2 = limiter.start("key")
        self.assertEqual(d2.called, False)
        d3 = limiter.start("key")
        self.assertEqual(d3.called, False)

        # Stop the first concurrent and check that the second fires.
        limiter.stop("key")
        self.assertEqual(d2.called, True)
        self.assertEqual(d3.called, False)

        # Stop the second concurrent and check that the third fires.
        limiter.stop("key")
        self.assertEqual(d3.called, True)

        # Stop the third concurrent and check that we don't hang on to state.
        limiter.stop("key")
        self.assertEqual(limiter._concurrency_limiters, {})

    def test_concurrency_limiter_two_limit(self):
        """
        ConcurrencyLimitManager fires the next deferred in the queue when
        stop() is called.
        """
        limiter = ConcurrencyLimitManager(2)
        d1 = limiter.start("key")
        self.assertEqual(d1.called, True)
        d2 = limiter.start("key")
        self.assertEqual(d2.called, True)
        d3 = limiter.start("key")
        self.assertEqual(d3.called, False)
        d4 = limiter.start("key")
        self.assertEqual(d4.called, False)

        # Stop a concurrent and check that the third fires.
        limiter.stop("key")
        self.assertEqual(d3.called, True)
        self.assertEqual(d4.called, False)

        # Stop a concurrent and check that the fourth fires.
        limiter.stop("key")
        self.assertEqual(d4.called, True)

        # Stop the last concurrents and check that we don't hang on to state.
        limiter.stop("key")
        limiter.stop("key")
        self.assertEqual(limiter._concurrency_limiters, {})

    def test_concurrency_limiter_multiple_keys(self):
        """
        ConcurrencyLimitManager handles different keys independently.
        """
        limiter = ConcurrencyLimitManager(1)
        d1a = limiter.start("key-a")
        self.assertEqual(d1a.called, True)
        d2a = limiter.start("key-a")
        self.assertEqual(d2a.called, False)
        d1b = limiter.start("key-b")
        self.assertEqual(d1b.called, True)
        d2b = limiter.start("key-b")
        self.assertEqual(d2b.called, False)

        # Stop "key-a" and check that the next "key-a" fires.
        limiter.stop("key-a")
        self.assertEqual(d2a.called, True)
        self.assertEqual(d2b.called, False)

        # Stop "key-b" and check that the next "key-b" fires.
        limiter.stop("key-b")
        self.assertEqual(d2b.called, True)

        # Stop the last concurrents and check that we don't hang on to state.
        limiter.stop("key-a")
        limiter.stop("key-b")
        self.assertEqual(limiter._concurrency_limiters, {})


class TestNoStreamingHTTPWorkerBase(VumiTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(
            AppWorkerHelper(NoStreamingHTTPWorker))

    @inlineCallbacks
    def start_app_worker(self, config_overrides={}):
        self.config = {
            'health_path': '/health/',
            'web_path': '/foo',
            'web_port': 0,
            'metrics_prefix': 'metrics_prefix.',
            'conversation_cache_ttl': 0,
        }
        self.config.update(config_overrides)
        self.app = yield self.app_helper.get_app_worker(self.config)
        self.addr = self.app.webserver.getHost()
        self.url = 'http://%s:%s%s' % (
            self.addr.host, self.addr.port, self.config['web_path'])

        # Mock server to test HTTP posting of inbound messages & events
        self.mock_push_server = MockHttpServer(self.handle_request)
        yield self.mock_push_server.start()
        self.add_cleanup(self.mock_push_server.stop)
        self.push_calls = DeferredQueue()

        self.conversation = yield self.create_conversation(
            self.get_message_url(), self.get_event_url(),
            ['token-1', 'token-2', 'token-3'])

        self.auth_headers = {
            'Authorization': ['Basic ' + base64.b64encode('%s:%s' % (
                self.conversation.user_account.key, 'token-1'))],
        }

        self._setup_wait_for_request()
        self.add_cleanup(self._wait_for_requests)

    def get_message_url(self):
        return self.mock_push_server.url

    def get_event_url(self):
        return self.mock_push_server.url

    @inlineCallbacks
    def start_retry_server(self):
        """ Start mock server to test retries with. """
        retry_queue = DeferredQueue()

        def handle_request(request):
            retry_queue.put(request)
            return NOT_DONE_YET

        mock_retry_server = MockHttpServer(handle_request)
        yield mock_retry_server.start()
        self.add_cleanup(mock_retry_server.stop)
        returnValue((mock_retry_server.url, retry_queue))

    @inlineCallbacks
    def create_conversation(self, message_url, event_url, tokens):
        config = {
            'http_api_nostream': {
                'api_tokens': tokens,
                'push_message_url': message_url,
                'push_event_url': event_url,
                'metric_store': 'metric_store',
            }
        }
        conv = yield self.app_helper.create_conversation(config=config)
        yield self.app_helper.start_conversation(conv)
        conversation = yield self.app_helper.get_conversation(conv.key)
        returnValue(conversation)

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

    def post_metrics(self, metric_data):
        url = '%s/%s/metrics.json' % (self.url, self.conversation.key)
        return http_request_full(
            url, json.dumps(metric_data), self.auth_headers, method='PUT')

    def assert_response_ok(self, response, reason):
        self.assertEqual(response.code, http.OK)
        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        data = json.loads(response.delivered_body)
        self.assertEqual(data, {
            "success": True,
            "reason": reason,
        })

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

    def assert_metrics_published(self, metrics, prefix=None):
        if prefix is None:
            prefix = "go.campaigns.test-0-user.stores.metric_store"

        self.assertEqual(
            self.app_helper.get_published_metrics_with_aggs(self.app),
            [("%s.%s" % (prefix, name), value, agg)
             for name, value, agg in metrics])

    def assert_retry(self, retry, url, method='POST', owner='test-0-user',
                     intervals=(300, 1800, 3600)):
        self.assertEqual(retry.method, "POST")
        headers = dict(retry.requestHeaders.getAllRawHeaders())
        self.assertEqual(
            headers['Content-Type'], ['application/json; charset=utf-8'])
        self.assertEqual(
            headers['X-Owner-Id'], [owner])
        body = json.loads(retry.content.read())
        retry_body = json.loads(body['request'].pop('body'))
        self.assertEqual(body, {
            'intervals': list(intervals),
            'request': {
                'url': url,
                'method': method,
                'headers': {
                    'Content-Type': ['application/json; charset=utf-8'],
                },
            },
        })
        return retry_body


class TestNoStreamingHTTPWorker(TestNoStreamingHTTPWorkerBase):

    @inlineCallbacks
    def test_missing_auth(self):
        yield self.start_app_worker()
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
        yield self.start_app_worker()
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
        yield self.start_app_worker()
        msg = {
            'to_addr': '+2345',
            'content': 'foo',
            'message_id': 'evil_id',
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
        self.assertEqual(sent_msg['to_addr'], sent_msg['to_addr'])
        self.assertEqual(sent_msg['helper_metadata'], {
            'go': {
                'conversation_key': self.conversation.key,
                'conversation_type': 'http_api_nostream',
                'user_account': self.conversation.user_account.key,
            },
        })
        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['to_addr'], msg['to_addr'])
        self.assertEqual(sent_msg['from_addr'], None)

    @inlineCallbacks
    def test_send_to_with_zero_worker_concurrency(self):
        """
        When the worker_concurrency_limit is set to zero, our requests will
        never complete.

        This is a hacky way to test that the concurrency limit is being applied
        without invasive changes to the app worker.
        """
        yield self.start_app_worker({'worker_concurrency_limit': 0})
        msg = {
            'to_addr': '+2345',
            'content': 'foo',
            'message_id': 'evil_id',
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        d = http_request_full(
            url, json.dumps(msg), self.auth_headers, method='PUT',
            timeout=0.2)

        yield self.assertFailure(d, HttpTimeoutError)

    @inlineCallbacks
    def test_send_to_within_content_length_limit(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
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
                'conversation_type': 'http_api_nostream',
                'user_account': self.conversation.user_account.key,
            },
        })
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['session_event'], None)
        self.assertEqual(sent_msg['to_addr'], '+1234')
        self.assertEqual(sent_msg['from_addr'], None)

    @inlineCallbacks
    def test_send_to_content_too_long(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
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
        yield self.start_app_worker()
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
        yield self.start_app_worker()
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
    def test_send_to_opted_out(self):
        yield self.start_app_worker()
        # Create optout for user
        vumi_api = self.app_helper.vumi_helper.get_vumi_api()
        optout_store = vumi_api.get_user_api(
            self.conversation.user_account.key).optout_store
        optout_store.new_opt_out('msisdn', '+5432', {'message_id': '111'})
        msg = {
            'to_addr': '+5432',
            'content': 'foo',
            'message_id': 'evil_id',
        }

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')

        self.assertEqual(response.code, http.BAD_REQUEST)
        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        put_msg = json.loads(response.delivered_body)
        self.assertEqual(put_msg['success'], False)
        self.assertEqual(
            put_msg['reason'], 'Recipient with msisdn +5432 has opted out')
        self.assertEqual(self.app_helper.get_dispatched_outbound(), [])

    @inlineCallbacks
    def test_send_to_opted_out_optouts_disabled(self):
        yield self.start_app_worker()
        # Create optout for user
        vumi_api = self.app_helper.vumi_helper.get_vumi_api()
        user_api = vumi_api.get_user_api(self.conversation.user_account.key)
        optout_store = user_api.optout_store
        optout_store.new_opt_out('msisdn', '+5432', {'message_id': '111'})
        msg = {
            'to_addr': '+5432',
            'content': 'foo',
            'message_id': 'evil_id',
        }

        # Disable optouts
        user_account = yield user_api.get_user_account()
        user_account.disable_optouts = True
        yield user_account.save()

        url = '%s/%s/messages.json' % (self.url, self.conversation.key)
        response = yield http_request_full(url, json.dumps(msg),
                                           self.auth_headers, method='PUT')

        self.assertEqual(response.code, http.OK)
        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        put_msg = json.loads(response.delivered_body)
        self.assertEqual(put_msg['to_addr'], msg['to_addr'])
        self.assertEqual(put_msg['content'], msg['content'])

        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], msg['to_addr'])
        self.assertEqual(sent_msg['content'], msg['content'])

    @inlineCallbacks
    def test_in_reply_to(self):
        yield self.start_app_worker()
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
                'conversation_type': 'http_api_nostream',
                'user_account': self.conversation.user_account.key,
            },
        })
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['session_event'], None)
        self.assertEqual(sent_msg['to_addr'], inbound_msg['from_addr'])
        self.assertEqual(sent_msg['from_addr'], '9292')

    @inlineCallbacks
    def test_in_reply_to_within_content_length_limit(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
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
                'conversation_type': 'http_api_nostream',
                'user_account': self.conversation.user_account.key,
            },
        })
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['session_event'], None)
        self.assertEqual(sent_msg['to_addr'], inbound_msg['from_addr'])
        self.assertEqual(sent_msg['from_addr'], '9292')

    @inlineCallbacks
    def test_in_reply_to_content_too_long(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
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
        yield self.start_app_worker()
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
        yield self.start_app_worker()
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
        yield self.start_app_worker()
        # create a message with no (None) conversation
        inbound_msg = self.app_helper.make_inbound('in 1', message_id='msg-1')
        vumi_api = self.app_helper.vumi_helper.get_vumi_api()
        yield vumi_api.mdb.add_inbound_message(inbound_msg)

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
        yield self.start_app_worker()
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
        yield self.start_app_worker()
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

        self.assertEqual(
            response.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        self.assertEqual(response.code, http.OK)
        put_msg = json.loads(response.delivered_body)
        [sent_msg] = self.app_helper.get_dispatched_outbound()

        # We do not respect the message_id that's been given.
        self.assertNotEqual(sent_msg['message_id'], msg['message_id'])
        self.assertEqual(sent_msg['message_id'], put_msg['message_id'])
        self.assertEqual(sent_msg['to_addr'], inbound_msg['from_addr'])
        self.assertEqual(sent_msg['from_addr'], '9292')

    @inlineCallbacks
    def test_metric_publishing(self):
        yield self.start_app_worker()
        response = yield self.post_metrics([
            ("vumi.test.v1", 1234, 'sum'),
            ("vumi.test.v2", 3456, 'avg'),
        ])
        self.assert_response_ok(response, "Metrics published")
        self.assert_metrics_published([
            ("vumi.test.v1", 1234, 'sum'),
            ("vumi.test.v2", 3456, 'avg'),
        ])

    @inlineCallbacks
    def test_metric_publishing_upper_case_aggregates(self):
        yield self.start_app_worker()
        response = yield self.post_metrics([
            ("vumi.test.v1", 1234, 'LAST'),
        ])
        self.assert_response_ok(response, "Metrics published")
        self.assert_metrics_published([
            ("vumi.test.v1", 1234, 'last'),
        ])

    @inlineCallbacks
    def test_metric_publishing_invalid_aggregate_type(self):
        yield self.start_app_worker()
        response = yield self.post_metrics([
            ("vumi.test.v1", 1234, None),
        ])
        self.assert_bad_request(response, "None is not a valid aggregate.")
        self.assert_metrics_published([])

    @inlineCallbacks
    def test_metrics_publishing_unknown_aggregate_name(self):
        yield self.start_app_worker()
        response = yield self.post_metrics([
            ("vumi.test.v1", 1234, "unknown"),
        ])
        self.assert_bad_request(
            response, "'unknown' is not a valid aggregate.")
        self.assert_metrics_published([])

    @inlineCallbacks
    def test_health_response(self):
        yield self.start_app_worker()
        health_url = 'http://%s:%s%s' % (
            self.addr.host, self.addr.port, self.config['health_path'])

        response = yield http_request_full(health_url, method='GET')
        self.assertEqual(response.delivered_body, 'OK')

    @inlineCallbacks
    def test_post_inbound_message(self):
        yield self.start_app_worker()
        msg_d = self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)

        req = yield self.push_calls.get()
        posted_json = req.content.read()
        self.assertEqual(
            req.requestHeaders.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        req.finish()
        msg = yield msg_d

        posted_msg = TransportUserMessage.from_json(posted_json)
        self.assertEqual(posted_msg['message_id'], msg['message_id'])

    @inlineCallbacks
    def test_post_inbound_message_ignored(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
            'ignore_messages': True,
        })
        yield self.conversation.save()

        yield self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)
        self.push_calls.put(None)
        req = yield self.push_calls.get()
        self.assertEqual(req, None)

    def _patch_http_request_full(self, exception_class):
        from go.apps.http_api_nostream import vumi_app
        http_calls = []

        def raiser(*args, **kw):
            http_calls.append((args, kw))
            raise exception_class()
        self.patch(vumi_app, 'http_request_full', raiser)
        return http_calls

    @inlineCallbacks
    def test_post_inbound_message_201_response(self):
        yield self.start_app_worker()
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
        yield self.start_app_worker()
        with LogCatcher(message='Got unexpected response code') as lc:
            msg_d = self.app_helper.make_dispatch_inbound(
                'in 1', message_id='1', conv=self.conversation)
            req = yield self.push_calls.get()
            req.setResponseCode(500)
            req.finish()
            yield msg_d
        [warning_log] = lc.messages()
        self.assertTrue(self.get_message_url() in warning_log)
        self.assertTrue('500' in warning_log)

    @inlineCallbacks
    def test_post_inbound_message_500_schedule_retry(self):
        retry_url, retry_calls = yield self.start_retry_server()
        yield self.start_app_worker({
            'http_retry_api': retry_url,
        })
        msg_d = self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)

        # return 500 response to message push
        req = yield self.push_calls.get()
        req.setResponseCode(500)
        req.finish()

        # catch and check retry
        retry = yield retry_calls.get()
        retry_msg = self.assert_retry(retry, self.get_message_url())
        retry.setResponseCode(200)
        retry.finish()

        with LogCatcher(log_level=logging.INFO) as lc:
            msg = yield msg_d

        self.assertEqual(lc.messages(), [
            "Successfully scheduled retry of request [account: u'test-0-user'"
            ", url: '%s']" % self.get_message_url(),
        ])

        self.assertEqual(retry_msg['message_id'], msg['message_id'])

    @inlineCallbacks
    def test_post_inbound_message_500_schedule_retry_failed_500(self):
        retry_url, retry_calls = yield self.start_retry_server()
        yield self.start_app_worker({
            'http_retry_api': retry_url,
        })
        msg_d = self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)

        # return 500 response to message push
        req = yield self.push_calls.get()
        req.setResponseCode(500)
        req.finish()

        # catch and check retry
        retry = yield retry_calls.get()
        retry_data = retry.content.read()
        retry.setResponseCode(500)
        retry.finish()

        with LogCatcher(log_level=logging.WARNING) as lc:
            yield msg_d

        self.assertEqual(lc.messages(), [
            "Failed to schedule retry request [account: u'test-0-user'"
            ", request: %r, response: [500, 'Internal Server Error']]"
            % (retry_data,),
        ])

    @inlineCallbacks
    def test_post_inbound_message_500_schedule_retry_exception(self):
        retry_url, retry_calls = yield self.start_retry_server()
        yield self.start_app_worker({
            'http_retry_api': retry_url,
        })
        msg_d = self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)

        # return 500 response to message push
        req = yield self.push_calls.get()
        req.setResponseCode(500)
        req.finish()

        class TestException(Exception):
            """Custom test exception."""

        http_calls = self._patch_http_request_full(TestException)

        with LogCatcher(log_level=logging.WARNING) as lc:
            yield msg_d

        [(_, http_kw)] = http_calls
        self.assertEqual(lc.messages(), [
            "Got unexpected response code 500 from %s"
            % self.get_message_url(),
            "Error scheduling retry of request [account: u'test-0-user'"
            ", request: %r, error: TestException()]" % (http_kw['data'],),
        ])

        self.assertEqual(retry_calls.pending, [])

    @inlineCallbacks
    def test_post_inbound_message_300_does_not_schedule_retry(self):
        retry_url, retry_calls = yield self.start_retry_server()
        yield self.start_app_worker({
            'http_retry_api': retry_url,
        })
        msg_d = self.app_helper.make_dispatch_inbound(
            'in 1', message_id='1', conv=self.conversation)

        # return 300 response to message push
        req = yield self.push_calls.get()
        req.setResponseCode(300)
        req.finish()

        with LogCatcher(log_level=logging.INFO) as lc:
            yield msg_d

        self.assertEqual(lc.messages(), [])
        self.assertEqual(retry_calls.pending, [])

    @inlineCallbacks
    def test_post_inbound_message_no_url(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
            'push_message_url': None,
        })
        yield self.conversation.save()

        msg_prefix = 'push_message_url not configured'
        with LogCatcher(message=msg_prefix, log_level=logging.WARNING) as lc:
            yield self.app_helper.make_dispatch_inbound(
                'in 1', message_id='1', conv=self.conversation)
            [url_not_configured_log] = lc.messages()
        self.assertTrue(self.conversation.key in url_not_configured_log)

    @inlineCallbacks
    def test_post_inbound_message_unsupported_scheme(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
            'push_message_url': 'example.com',
        })
        yield self.conversation.save()

        self._patch_http_request_full(SchemeNotSupported)
        with LogCatcher(message='Unsupported') as lc:
            yield self.app_helper.make_dispatch_inbound(
                'in 1', message_id='1', conv=self.conversation)
            [unsupported_scheme_log] = lc.messages()
        self.assertTrue('example.com' in unsupported_scheme_log)

    @inlineCallbacks
    def test_post_inbound_message_timeout(self):
        yield self.start_app_worker()
        self._patch_http_request_full(HttpTimeoutError)
        with LogCatcher(message='Timeout') as lc:
            yield self.app_helper.make_dispatch_inbound(
                'in 1', message_id='1', conv=self.conversation)
            [timeout_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in timeout_log)

    @inlineCallbacks
    def test_post_inbound_message_dns_lookup_error(self):
        yield self.start_app_worker()
        self._patch_http_request_full(DNSLookupError)
        with LogCatcher(message='DNS lookup error') as lc:
            yield self.app_helper.make_dispatch_inbound(
                'in 1', message_id='1', conv=self.conversation)
            [dns_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in dns_log)

    @inlineCallbacks
    def test_post_inbound_message_connection_refused_error(self):
        yield self.start_app_worker()
        self._patch_http_request_full(ConnectionRefusedError)
        with LogCatcher(message='Connection refused') as lc:
            yield self.app_helper.make_dispatch_inbound(
                'in 1', message_id='1', conv=self.conversation)
            [dns_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in dns_log)

    @inlineCallbacks
    def test_post_inbound_event(self):
        yield self.start_app_worker()
        msg1 = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        event_d = self.app_helper.make_dispatch_ack(
            msg1, conv=self.conversation)

        req = yield self.push_calls.get()
        posted_json_data = req.content.read()
        self.assertEqual(
            req.requestHeaders.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        req.finish()
        ack1 = yield event_d

        self.assertEqual(TransportEvent.from_json(posted_json_data), ack1)

    @inlineCallbacks
    def test_post_inbound_event_ignored(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
            'ignore_events': True,
        })
        yield self.conversation.save()

        msg1 = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')
        yield self.app_helper.make_dispatch_ack(
            msg1, conv=self.conversation)
        self.push_calls.put(None)
        req = yield self.push_calls.get()
        self.assertEqual(req, None)

    @inlineCallbacks
    def test_post_inbound_event_no_url(self):
        yield self.start_app_worker()
        self.conversation.config['http_api_nostream'].update({
            'push_event_url': None,
        })
        yield self.conversation.save()

        msg1 = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')

        msg_prefix = 'push_event_url not configured'
        with LogCatcher(message=msg_prefix, log_level=logging.INFO) as lc:
            yield self.app_helper.make_dispatch_ack(
                msg1, conv=self.conversation)
            [url_not_configured_log] = lc.messages()
        self.assertTrue(self.conversation.key in url_not_configured_log)

    @inlineCallbacks
    def test_post_inbound_event_timeout(self):
        yield self.start_app_worker()
        msg1 = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')

        self._patch_http_request_full(HttpTimeoutError)
        with LogCatcher(message='Timeout') as lc:
            yield self.app_helper.make_dispatch_ack(
                msg1, conv=self.conversation)
            [timeout_log] = lc.messages()
        self.assertTrue(timeout_log.endswith(self.mock_push_server.url))

    @inlineCallbacks
    def test_post_inbound_event_dns_lookup_error(self):
        yield self.start_app_worker()
        msg1 = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')

        self._patch_http_request_full(DNSLookupError)
        with LogCatcher(message='DNS lookup error') as lc:
            yield self.app_helper.make_dispatch_ack(
                msg1, conv=self.conversation)
            [dns_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in dns_log)

    @inlineCallbacks
    def test_post_inbound_event_connection_refused_error(self):
        yield self.start_app_worker()
        msg1 = yield self.app_helper.make_stored_outbound(
            self.conversation, 'out 1', message_id='1')

        self._patch_http_request_full(ConnectionRefusedError)
        with LogCatcher(message='Connection refused') as lc:
            yield self.app_helper.make_dispatch_ack(
                msg1, conv=self.conversation)
            [dns_log] = lc.messages()
        self.assertTrue(self.mock_push_server.url in dns_log)

    @inlineCallbacks
    def test_bad_urls(self):
        def assert_not_found(url, headers={}):
            d = http_request_full(self.url, method='GET', headers=headers)
            d.addCallback(lambda r: self.assertEqual(r.code, http.NOT_FOUND))
            return d

        yield self.start_app_worker()

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
        yield self.start_app_worker()
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
        yield self.start_app_worker()
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


class TestNoStreamingHTTPWorkerWithAuth(TestNoStreamingHTTPWorkerBase):

    def get_message_url(self):
        parse_result = urlparse(self.mock_push_server.url)
        return urlunparse((
            parse_result.scheme,
            'username:password@%s:%s' % (
                parse_result.hostname, parse_result.port),
            parse_result.path,
            parse_result.params,
            parse_result.query,
            parse_result.fragment))

    @inlineCallbacks
    def test_push_with_basic_auth(self):
        yield self.start_app_worker()
        self.app_helper.make_dispatch_inbound(
            'in', message_id='1', conv=self.conversation)
        req = yield self.push_calls.get()
        req.finish()
        [header] = req.requestHeaders.getRawHeaders('Authorization')
        self.assertEqual(
            header, 'Basic %s' % (base64.b64encode('username:password')))
