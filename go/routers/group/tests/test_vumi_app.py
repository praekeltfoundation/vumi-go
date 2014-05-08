from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.routers.group.vumi_app import GroupRouter
from go.routers.tests.helpers import RouterWorkerHelper


class TestGroupRouter(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.router_helper = self.add_helper(RouterWorkerHelper(GroupRouter))
        self.router_worker = yield self.router_helper.get_router_worker({})

    @inlineCallbacks
    def assert_routed_inbound(self, from_addr, router, expected_endpoint):
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            "hello", from_addr=from_addr, router=router)
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
        yield self.assert_routed_inbound("from_addr", router, 'default')

    @inlineCallbacks
    def test_inbound_no_contact(self):
        """
        If the message has no associated contact, it should be dispatched to
        the `default` endpoint.
        """
        group = yield self.router_helper.create_group(u"group")
        router = yield self.router_helper.create_router(started=True, config={
            'rules': [
                {'group': group.key, 'endpoint': 'group_ep'},
            ]})
        yield self.assert_routed_inbound("+27831234567", router, 'default')

    @inlineCallbacks
    def test_inbound_contact_not_in_group(self):
        """
        If the message is from a contact in no groups, it should be dispatched
        to the `default` endpoint.
        """
        group = yield self.router_helper.create_group(u"group")
        contact = yield self.router_helper.create_contact(u"+27831234567")
        router = yield self.router_helper.create_router(started=True, config={
            'rules': [
                {'group': group.key, 'endpoint': 'group_ep'},
            ]})
        yield self.assert_routed_inbound(contact.msisdn, router, 'default')

    @inlineCallbacks
    def test_inbound_contact_in_group(self):
        """
        If the message is from a contact in a configured group, it should be
        dispatched to the appropriate endpoint.
        """
        group = yield self.router_helper.create_group(u"group")
        contact = yield self.router_helper.create_contact(
            u"+27831234567", groups=[group])
        router = yield self.router_helper.create_router(started=True, config={
            'rules': [
                {'group': group.key, 'endpoint': 'group_ep'},
            ]})
        yield self.assert_routed_inbound(contact.msisdn, router, 'group_ep')

    @inlineCallbacks
    def test_inbound_contact_in_multiple_groups(self):
        """
        If the message is from a contact in multiple configured groups, it
        should be dispatched to the endpoint in the first matching rule.
        """
        # We use lots of groups here to decrease the false positive chance.
        groups = [(yield self.router_helper.create_group(u"group%s" % i))
                  for i in range(10)]
        contact = yield self.router_helper.create_contact(
            u"+27831234567", groups=groups[2:])
        router = yield self.router_helper.create_router(started=True, config={
            'rules': [
                {'group': group.key, 'endpoint': '%s_ep' % group.name}
                for group in groups
            ]})
        yield self.assert_routed_inbound(contact.msisdn, router, 'group2_ep')
