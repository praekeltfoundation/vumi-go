from twisted.internet.defer import inlineCallbacks

from go.vumitools.tests.utils import RouterWorkerTestCase
from go.vumitools.routing import RoutingMetadata
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
    def assert_routed_event(self, event, router, expected_endpoint):
        yield self.dispatch_event_to_router(event, router)
        eevent = event.copy()
        eevent.set_routing_endpoint(expected_endpoint)
        [revent] = self.get_dispatched_events('ro_conn')
        self.assertEqual(eevent, revent)

    def set_event_hops(self, event, outbound_hops, num_inbound_hops=1):
        rmeta = RoutingMetadata(event)
        rmeta.set_outbound_hops(outbound_hops)
        rev_hops = reversed(outbound_hops[-num_inbound_hops:])
        for outbound_src, outbound_dst in rev_hops:
            rmeta.push_hop(outbound_dst, outbound_src)

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

    @inlineCallbacks
    def test_event_default_to_default(self):
        router = yield self.setup_router({
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        ack = self.mkmsg_ack()
        self.add_router_md_to_msg(ack, router, 'default')
        self.set_event_hops(ack, [
            [['app1', 'default'], ['kwr1', 'default']],
            [['kwr1', 'default'], ['sphex', 'default']],
        ])
        yield self.assert_routed_event(ack, router, 'default')

    @inlineCallbacks
    def test_event_foo_to_default(self):
        router = yield self.setup_router({
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        ack = self.mkmsg_ack()
        self.add_router_md_to_msg(ack, router, 'foo')
        self.set_event_hops(ack, [
            [['app1', 'default'], ['kwr1', 'default']],
            [['kwr1', 'foo'], ['sphex', 'default']],
        ])
        yield self.assert_routed_event(ack, router, 'default')

    @inlineCallbacks
    def test_event_default_to_foo(self):
        router = yield self.setup_router({
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        ack = self.mkmsg_ack()
        self.add_router_md_to_msg(ack, router, 'default')
        self.set_event_hops(ack, [
            [['app1', 'default'], ['kwr1', 'foo']],
            [['kwr1', 'default'], ['sphex', 'default']],
        ])
        yield self.assert_routed_event(ack, router, 'foo')

    @inlineCallbacks
    def test_event_foo_to_bar(self):
        router = yield self.setup_router({
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        ack = self.mkmsg_ack()
        self.add_router_md_to_msg(ack, router, 'foo')
        self.set_event_hops(ack, [
            [['app1', 'default'], ['kwr1', 'bar']],
            [['kwr1', 'foo'], ['sphex', 'default']],
        ])
        yield self.assert_routed_event(ack, router, 'bar')
