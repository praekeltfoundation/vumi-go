from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.routers.group.vumi_app import GroupRouter
from go.routers.tests.helpers import RouterWorkerHelper


class TestGroupRouter(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.router_helper = self.add_helper(RouterWorkerHelper(GroupRouter))
        self.router_worker = yield self.router_helper.get_router_worker({})
        self.persistence_helper = self.add_helper(PersistenceHelper())

        rules = []
        for i in [1, 2]:
            group = yield self.router_helper.create_group(
                unicode("group-%i" % i))
            yield self.router_helper.create_contact(
                u"+2772438517%i" % i,
                name=u"John",
                surname=u"Smith",
                groups=[group]
            )
            rules.append({
                'group': group.key,
                'endpoint': "endpoint-%i" % i
            })
        self.router_config = {
            'rules': rules
        }

    @inlineCallbacks
    def assert_routed_inbound(self, content, router, expected_endpoint):
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            content, router=router)
        emsg = msg.copy()
        emsg.set_routing_endpoint(expected_endpoint)
        rmsg = self.router_helper.ro.get_dispatched_inbound()[-1]
        self.assertEqual(emsg, rmsg)

    @inlineCallbacks
    def test_start(self):
        router = yield self.router_helper.create_router()
        self.assertTrue(router.stopped())
        self.assertFalse(router.running())

        yield self.router_helper.start_router(router)
        router = yield self.router_helper.get_router(router.key)
        self.assertFalse(router.stopped())
        self.assertTrue(router.running())

    @inlineCallbacks
    def test_inbound_no_config(self):
        router = yield self.router_helper.create_router(started=True)
        yield self.assert_routed_inbound("foo bar", router, 'default')
        yield self.assert_routed_inbound("baz quux", router, 'default')

    @inlineCallbacks
    def test_route_on_group(self):
        router = yield self.router_helper.create_router(
            started=True, config=self.router_config)
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            "hello", router=router, from_addr=u"+27724385171")
        emsg = msg.copy()
        emsg.set_routing_endpoint("endpoint-1")
        rmsg = self.router_helper.ro.get_dispatched_inbound()[-1]
        self.assertEqual(emsg, rmsg)
