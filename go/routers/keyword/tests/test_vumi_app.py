from twisted.internet.defer import inlineCallbacks

from go.vumitools.tests.utils import RouterWorkerTestCase
from go.routers.keyword.vumi_app import KeywordRouter


class TestKeywordRouter(RouterWorkerTestCase):

    application_class = KeywordRouter

    @inlineCallbacks
    def setUp(self):
        super(TestKeywordRouter, self).setUp()

        self.config = self.mk_config({})
        worker = yield self.get_router_worker(self.config)
        self.vumi_api = worker.vumi_api
        user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_account_key = user_account.key
        self.user_api = self.vumi_api.get_user_api(self.user_account_key)

    @inlineCallbacks
    def assert_routed_inbound(self, msg, router, expected_endpoint):
        yield self.dispatch_inbound_to_router(msg, router)
        emsg = msg.copy()
        emsg.set_routing_endpoint(expected_endpoint)
        rmsg = self.get_dispatched_inbound('ro_conn')[-1]
        self.assertEqual(emsg, rmsg)

    @inlineCallbacks
    def assert_routed_outbound(self, msg, router, src_endpoint):
        yield self.dispatch_outbound_to_router(msg, router, src_endpoint)
        emsg = msg.copy()
        emsg.set_routing_endpoint('default')
        rmsg = self.get_dispatched_outbound('ri_conn')[-1]
        self.assertEqual(emsg, rmsg)

    @inlineCallbacks
    def test_inbound_no_config(self):
        router = yield self.setup_router({})
        yield self.assert_routed_inbound(
            self.mkmsg_in("foo bar"), router, 'default')
        yield self.assert_routed_inbound(
            self.mkmsg_in("baz quux"), router, 'default')

    @inlineCallbacks
    def test_inbound_simple_keyword(self):
        router = yield self.setup_router({
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        yield self.assert_routed_inbound(
            self.mkmsg_in("foo bar"), router, 'app1')
        yield self.assert_routed_inbound(
            self.mkmsg_in("baz quux"), router, 'default')
        yield self.assert_routed_inbound(
            self.mkmsg_in(" FoO bar"), router, 'app1')

    @inlineCallbacks
    def test_inbound_regex_keyword(self):
        router = yield self.setup_router({
            'keyword_endpoint_mapping': {
                'f[o0]+': 'app1',
            },
        })
        yield self.assert_routed_inbound(
            self.mkmsg_in("fo bar"), router, 'app1')
        yield self.assert_routed_inbound(
            self.mkmsg_in("baz quux"), router, 'default')
        yield self.assert_routed_inbound(
            self.mkmsg_in(" Fo0O bar"), router, 'app1')

    @inlineCallbacks
    def test_outbound_no_config(self):
        router = yield self.setup_router({})
        yield self.assert_routed_outbound(
            self.mkmsg_in("foo bar"), router, 'default')
        yield self.assert_routed_outbound(
            self.mkmsg_in("baz quux"), router, 'default')
        yield self.assert_routed_outbound(
            self.mkmsg_in("foo bar"), router, 'app1')
        yield self.assert_routed_outbound(
            self.mkmsg_in("baz quux"), router, 'app1')

    @inlineCallbacks
    def test_outbound(self):
        router = yield self.setup_router({
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        yield self.assert_routed_outbound(
            self.mkmsg_in("foo bar"), router, 'default')
        yield self.assert_routed_outbound(
            self.mkmsg_in("baz quux"), router, 'default')
        yield self.assert_routed_outbound(
            self.mkmsg_in("foo bar"), router, 'app1')
        yield self.assert_routed_outbound(
            self.mkmsg_in("baz quux"), router, 'app1')
