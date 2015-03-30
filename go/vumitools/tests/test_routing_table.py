import copy

from vumi.tests.helpers import VumiTestCase
from vumi.tests.utils import LogCatcher

from go.vumitools.routing_table import (
    RoutingTable, GoConnector, GoConnectorError)


class FakeConversation(object):
    """Fake conversation with the appropriate properties used for routing.
    """

    def __init__(self, conversation_type, key):
        self.conversation_type = conversation_type
        self.key = key

    def get_connector(self):
        return GoConnector.for_model(self)


class FakeRouter(object):
    """Fake router with the appropriate properties used for routing.
    """

    def __init__(self, router_type, key):
        self.router_type = router_type
        self.key = key

    def get_inbound_connector(self):
        return GoConnector.for_model(self, GoConnector.INBOUND)

    def get_outbound_connector(self):
        return GoConnector.for_model(self, GoConnector.OUTBOUND)


class FakePlasticChannel(object):
    """Fake channel with the appropriate properties used for routing.
    """

    def __init__(self, tagpool, tag):
        self.tagpool = tagpool
        self.tag = tag

    def get_connector(self):
        return GoConnector.for_model(self)


class TestRoutingTable(VumiTestCase):

    CONV_1 = "CONVERSATION:dummy:1"
    CONV_2 = "CONVERSATION:dummy:2"
    CHANNEL_2 = "TRANSPORT_TAG:pool:tag2"
    CHANNEL_3 = "TRANSPORT_TAG:pool:tag3"
    ROUTER_1_INBOUND = "ROUTER:dummy:1:INBOUND"
    ROUTER_1_OUTBOUND = "ROUTER:dummy:1:OUTBOUND"

    DEFAULT_ROUTING = {
        CONV_1: {
            "default1.1": [CHANNEL_2, "default2"],
            "default1.2": [CHANNEL_3, "default3"],
        }
    }

    COMPLEX_ROUTING = {
        CHANNEL_2: {
            "default": [ROUTER_1_INBOUND, "default"],
        },
        ROUTER_1_INBOUND: {
            "default": [CHANNEL_2, "default"],
        },
        ROUTER_1_OUTBOUND: {
            "keyword1": [CONV_1, "default"],
            "keyword2": [CONV_2, "default"],
        },
        CONV_1: {
            "default": [ROUTER_1_OUTBOUND, "keyword1"],
        },
        CONV_2: {
            "default": [ROUTER_1_OUTBOUND, "keyword2"],
            "sms": [CHANNEL_3, "default"],
        },
    }

    def make_rt(self, routing_table=None):
        if routing_table is None:
            routing_table = copy.deepcopy(self.DEFAULT_ROUTING)
        return RoutingTable(routing_table)

    def assert_routing_entries(self, routing_table, expected_entries):
        self.assertEqual(
            sorted(routing_table.entries()),
            sorted((GoConnector.parse(str(sc)), se,
                    GoConnector.parse(str(dc)), de)
                   for sc, se, dc, de in expected_entries))

    def assert_connectors(self, connectors, expected_connectors):
        self.assertEqual(sorted(connectors), sorted(
            GoConnector.parse(str(conn)) for conn in expected_connectors))

    def test_lookup_target(self):
        rt = self.make_rt()
        self.assertEqual(rt.lookup_target(self.CONV_1, "default1.1"),
                         [GoConnector.parse(self.CHANNEL_2), "default2"])
        self.assertEqual(rt.lookup_target(self.CONV_1, "default1.2"),
                         [GoConnector.parse(self.CHANNEL_3), "default3"])

    def test_lookup_unknown_target(self):
        rt = self.make_rt()
        self.assertEqual(rt.lookup_target(self.CHANNEL_3, "default3"),
                         None)

    def test_lookup_source(self):
        rt = self.make_rt()
        self.assertEqual(rt.lookup_source(self.CHANNEL_2, "default2"),
                         [GoConnector.parse(self.CONV_1), "default1.1"])
        self.assertEqual(rt.lookup_source(self.CHANNEL_3, "default3"),
                         [GoConnector.parse(self.CONV_1), "default1.2"])

    def test_lookup_unknown_source(self):
        rt = self.make_rt()
        self.assertEqual(rt.lookup_source(self.CONV_1, "default1.1"),
                         None)

    def test_lookup_targets(self):
        rt = self.make_rt()
        self.assertEqual(sorted(rt.lookup_targets(self.CONV_1)), [
            ("default1.1", [GoConnector.parse(self.CHANNEL_2), "default2"]),
            ("default1.2", [GoConnector.parse(self.CHANNEL_3), "default3"]),
        ])

    def test_lookup_sources(self):
        rt = self.make_rt()
        self.assertEqual(sorted(rt.lookup_sources(self.CHANNEL_3)), [
            ("default3", [GoConnector.parse(self.CONV_1), "default1.2"]),
        ])

    def test_entries(self):
        rt = self.make_rt()
        self.assert_routing_entries(rt, [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_add_entry(self):
        rt = self.make_rt()
        tag_conn = 'TRANSPORT_TAG:new:tag1'
        conv_conn = 'CONVERSATION:new:12345'
        rt.add_entry(tag_conn, "default4", conv_conn, "default5")
        self.assert_routing_entries(rt, [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
            (tag_conn, "default4", conv_conn, "default5"),
        ])

    def test_add_entry_that_exists(self):
        rt = self.make_rt()
        tag_conn = 'TRANSPORT_TAG:new:tag1'
        with LogCatcher() as lc:
            rt.add_entry(self.CONV_1, "default1.2", tag_conn, "default4")
            self.assertEqual(lc.messages(), [
                "Replacing routing entry for ('%s', 'default1.2'):"
                " was ['%s', 'default3'], now ['%s', 'default4']" % (
                    self.CONV_1, self.CHANNEL_3, tag_conn)
            ])
        self.assert_routing_entries(rt, [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", tag_conn, "default4"),
        ])

    def test_add_invalid_entry(self):
        rt = self.make_rt()
        self.assertRaises(
            ValueError, rt.add_entry, self.CONV_1, "foo", self.CONV_2, "bar")
        self.assert_routing_entries(rt, [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_remove_entry(self):
        rt = self.make_rt()
        rt.remove_entry(self.CONV_1, "default1.1")
        self.assert_routing_entries(rt, [
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_remove_entry_that_does_not_exist(self):
        rt = self.make_rt()
        with LogCatcher() as lc:
            rt.remove_entry(self.CONV_1, "default1.unknown")
            self.assertEqual(lc.messages(), [
                "Attempting to remove missing routing entry for"
                " ('%s', 'default1.unknown')." % (self.CONV_1,)
            ])
        self.assert_routing_entries(rt, [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_remove_endpoint(self):
        rt = self.make_rt({
            self.CONV_1: {
                "default1.1": [self.CHANNEL_2, "default2"],
                "default1.2": [self.CHANNEL_3, "default3"]
            },
            self.CHANNEL_2: {
                "default2": [self.CONV_1, "default1.1"],
            },
            self.CHANNEL_3: {
                "default3": [self.CONV_2, "default"],
            },
        })

        rt.remove_endpoint(self.CONV_1, "default1.1")

        self.assert_routing_entries(rt, [
            (self.CONV_1, 'default1.2', self.CHANNEL_3, 'default3'),
            (self.CHANNEL_3, 'default3', self.CONV_2, 'default')
        ])

    def test_remove_connector_source(self):
        rt = self.make_rt()
        rt.remove_connector(self.CONV_1)
        self.assert_routing_entries(rt, [])

    def test_remove_connector_destination(self):
        rt = self.make_rt()
        rt.remove_connector(self.CHANNEL_2)
        self.assert_routing_entries(rt, [
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_remove_conversation(self):
        rt = self.make_rt({})
        conv = FakeConversation("conv_type_1", "12345")
        conv_conn = str(
            GoConnector.for_conversation(conv.conversation_type, conv.key))
        rt.add_entry(conv_conn, "default", self.CHANNEL_2, "default")
        rt.add_entry(self.CHANNEL_2, "default", conv_conn, "default")
        rt.remove_conversation(conv)
        self.assert_routing_entries(rt, [])

    def test_remove_router(self):
        rt = self.make_rt({})
        router = FakeRouter("router_1", "12345")
        rin_conn = str(GoConnector.for_router(
            router.router_type, router.key, GoConnector.INBOUND))
        rout_conn = str(GoConnector.for_router(
            router.router_type, router.key, GoConnector.OUTBOUND))
        rt.add_entry(self.CHANNEL_2, 'default', rin_conn, 'default')
        rt.add_entry(rin_conn, 'default', self.CHANNEL_2, 'default')
        rt.add_entry(self.CONV_1, 'default', rout_conn, 'default')
        rt.add_entry(rout_conn, 'default', self.CONV_1, 'default')
        self.assertNotEqual(list(rt.entries()), [])
        rt.remove_router(router)
        self.assert_routing_entries(rt, [])

    def test_remove_transport_tag(self):
        tag = ["pool1", "tag1"]
        rt = self.make_rt({})
        tag_conn = str(GoConnector.for_transport_tag(*tag))
        rt.add_entry(tag_conn, "default", self.CONV_1, "default")
        rt.add_entry(self.CONV_1, "default", tag_conn, "default")
        rt.remove_transport_tag(tag)
        self.assert_routing_entries(rt, [])

    def test_transitive_targets_simple_case(self):
        rt = self.make_rt()
        self.assert_connectors(rt.transitive_targets(self.CONV_1), [
            self.CHANNEL_2, self.CHANNEL_3,
        ])

    def test_transitive_targets_with_routers(self):
        rt = self.make_rt(self.COMPLEX_ROUTING)
        self.assert_connectors(rt.transitive_targets(self.CHANNEL_2), [
            self.CONV_1, self.CONV_2, self.ROUTER_1_INBOUND,
        ])
        self.assert_connectors(rt.transitive_targets(self.CHANNEL_3), [
        ])
        self.assert_connectors(rt.transitive_targets(self.CONV_1), [
            self.ROUTER_1_OUTBOUND, self.CHANNEL_2,
        ])
        self.assert_connectors(rt.transitive_targets(self.CONV_2), [
            self.ROUTER_1_OUTBOUND, self.CHANNEL_2, self.CHANNEL_3,
        ])
        self.assert_connectors(rt.transitive_targets(self.ROUTER_1_INBOUND),
                               [self.CHANNEL_2])
        self.assert_connectors(rt.transitive_targets(self.ROUTER_1_OUTBOUND),
                               [self.CONV_1, self.CONV_2])

    def test_transitive_sources_simple_case(self):
        rt = self.make_rt()
        self.assert_connectors(rt.transitive_sources(self.CHANNEL_2), [
            self.CONV_1,
        ])

    def test_transitive_sources_with_routers(self):
        rt = self.make_rt(self.COMPLEX_ROUTING)
        self.assert_connectors(rt.transitive_sources(self.CHANNEL_2), [
            self.CONV_1, self.CONV_2, self.ROUTER_1_INBOUND,
        ])
        self.assert_connectors(rt.transitive_sources(self.CHANNEL_3), [
            self.CONV_2,
        ])
        self.assert_connectors(rt.transitive_sources(self.CONV_1), [
            self.ROUTER_1_OUTBOUND, self.CHANNEL_2,
        ])
        self.assert_connectors(rt.transitive_sources(self.CONV_2), [
            self.ROUTER_1_OUTBOUND, self.CHANNEL_2,
        ])
        self.assert_connectors(rt.transitive_sources(self.ROUTER_1_INBOUND),
                               [self.CHANNEL_2])
        self.assert_connectors(rt.transitive_sources(self.ROUTER_1_OUTBOUND),
                               [self.CONV_1, self.CONV_2])

    def test_entry_validation(self):
        rt = self.make_rt()

        def validate(src_conn, dst_conn):
            rt.validate_entry(src_conn, "default", dst_conn, "default")

        def assert_invalid(src_conn, dst_conn):
            self.assertRaises(ValueError, validate, src_conn, dst_conn)

        validate(self.CONV_1, self.CHANNEL_2)
        validate(self.CHANNEL_2, self.CONV_1)
        validate(self.CONV_1, self.ROUTER_1_OUTBOUND)
        validate(self.ROUTER_1_OUTBOUND, self.CONV_1)
        validate(self.ROUTER_1_INBOUND, self.CHANNEL_2)
        validate(self.CHANNEL_2, self.ROUTER_1_INBOUND)

        assert_invalid(self.CONV_1, self.CONV_1)
        assert_invalid(self.CHANNEL_2, self.CHANNEL_2)
        assert_invalid(self.CONV_1, self.ROUTER_1_INBOUND)
        assert_invalid(self.ROUTER_1_INBOUND, self.CONV_1)
        assert_invalid(self.ROUTER_1_OUTBOUND, self.CHANNEL_2)
        assert_invalid(self.CHANNEL_2, self.ROUTER_1_OUTBOUND)

    def test_validate_all_entries(self):
        rt = self.make_rt({})

        def add_entry(src_conn, src_endpoint, dst_conn, dst_endpoint):
            # This allows us to add invalid entries.
            connector_dict = rt._routing_table.setdefault(src_conn, {})
            connector_dict[src_endpoint] = [dst_conn, dst_endpoint]

        rt.validate_all_entries()

        add_entry(self.CHANNEL_2, "default", self.CONV_1, "default")
        rt.validate_all_entries()

        add_entry(self.ROUTER_1_INBOUND, "default", self.CONV_1, "foo")
        self.assertRaises(ValueError, rt.validate_all_entries)

        rt.remove_entry(self.ROUTER_1_INBOUND, "default")
        rt.validate_all_entries()

        add_entry(self.ROUTER_1_OUTBOUND, "default", self.CONV_1, "foo")
        rt.validate_all_entries()

        add_entry(self.CONV_1, "bar", self.CONV_1, "baz")
        self.assertRaises(ValueError, rt.validate_all_entries)


class TestGoConnector(VumiTestCase):
    def test_create_conversation_connector(self):
        c = GoConnector.for_conversation("conv_type_1", "12345")
        self.assertEqual(c.ctype, GoConnector.CONVERSATION)
        self.assertEqual(c.conv_type, "conv_type_1")
        self.assertEqual(c.conv_key, "12345")
        self.assertEqual(str(c), "CONVERSATION:conv_type_1:12345")

    def test_create_router_connector(self):
        c = GoConnector.for_router("rb_type_1", "12345",
                                          GoConnector.INBOUND)
        self.assertEqual(c.ctype, GoConnector.ROUTER)
        self.assertEqual(c.router_type, "rb_type_1")
        self.assertEqual(c.router_key, "12345")
        self.assertEqual(c.direction, GoConnector.INBOUND)
        self.assertEqual(str(c), "ROUTER:rb_type_1:12345:INBOUND")

    def test_create_transport_tag_connector(self):
        c = GoConnector.for_transport_tag("tagpool_1", "tag_1")
        self.assertEqual(c.ctype, GoConnector.TRANSPORT_TAG)
        self.assertEqual(c.tagpool, "tagpool_1")
        self.assertEqual(c.tagname, "tag_1")
        self.assertEqual(str(c), "TRANSPORT_TAG:tagpool_1:tag_1")

    def test_create_opt_out_connector(self):
        c = GoConnector.for_opt_out()
        self.assertEqual(c.ctype, GoConnector.OPT_OUT)
        self.assertEqual(str(c), "OPT_OUT")

    def test_parse_conversation_connector(self):
        c = GoConnector.parse("CONVERSATION:conv_type_1:12345")
        self.assertEqual(c.ctype, GoConnector.CONVERSATION)
        self.assertEqual(c.conv_type, "conv_type_1")
        self.assertEqual(c.conv_key, "12345")

    def test_parse_router_connector(self):
        c = GoConnector.parse("ROUTER:rb_type_1:12345:OUTBOUND")
        self.assertEqual(c.ctype, GoConnector.ROUTER)
        self.assertEqual(c.router_type, "rb_type_1")
        self.assertEqual(c.router_key, "12345")
        self.assertEqual(c.direction, GoConnector.OUTBOUND)

    def test_parse_transport_tag_connector(self):
        c = GoConnector.parse("TRANSPORT_TAG:tagpool_1:tag_1")
        self.assertEqual(c.ctype, GoConnector.TRANSPORT_TAG)
        self.assertEqual(c.tagpool, "tagpool_1")
        self.assertEqual(c.tagname, "tag_1")

    def test_parse_opt_out_connector(self):
        c = GoConnector.parse("OPT_OUT")
        self.assertEqual(c.ctype, GoConnector.OPT_OUT)

    def test_parse_unknown_ctype(self):
        self.assertRaises(GoConnectorError, GoConnector.parse,
                          "FOO:tagpool:tag")

    def test_parse_bad_parts(self):
        self.assertRaises(GoConnectorError, GoConnector.parse,
                          "CONVERSATION:foo")  # one part
        self.assertRaises(GoConnectorError, GoConnector.parse,
                          "CONVERSATION:foo:bar:baz")  # three parts

    def test_flip_router_connector(self):
        c1 = GoConnector.for_router(
            "dummy", "1", GoConnector.INBOUND)
        c2 = c1.flip_direction()
        self.assertEqual(c2.direction, GoConnector.OUTBOUND)
        self.assertEqual(c2.ctype, GoConnector.ROUTER)
        self.assertEqual(c2.router_type, "dummy")
        self.assertEqual(c2.router_key, "1")
        c3 = c2.flip_direction()
        self.assertEqual(c3.direction, GoConnector.INBOUND)

    def test_flip_non_router_connector(self):
        c = GoConnector.for_conversation("dummy", "1")
        self.assertRaises(GoConnectorError, c.flip_direction)

    def test_connector_direction(self):
        def assert_inbound(conn):
            self.assertEqual(GoConnector.INBOUND, conn.direction)

        def assert_outbound(conn):
            self.assertEqual(GoConnector.OUTBOUND, conn.direction)

        assert_inbound(GoConnector.for_opt_out())
        assert_inbound(GoConnector.for_conversation("conv_type_1", "12345"))
        assert_outbound(GoConnector.for_transport_tag("tagpool_1", "tag_1"))
        assert_inbound(
            GoConnector.for_router("rb_type_1", "12345", GoConnector.INBOUND))
        assert_outbound(
            GoConnector.for_router("rb_type_1", "12345", GoConnector.OUTBOUND))

    def test_create_conversation_connector_for_model(self):
        c = GoConnector.for_model(FakeConversation("conv_type_1", "12345"))
        self.assertEqual(c.ctype, GoConnector.CONVERSATION)
        self.assertEqual(c.conv_type, "conv_type_1")
        self.assertEqual(c.conv_key, "12345")
        self.assertEqual(str(c), "CONVERSATION:conv_type_1:12345")

    def test_create_router_connector_for_model(self):
        c = GoConnector.for_model(
            FakeRouter("rb_type_1", "12345"), GoConnector.INBOUND)
        self.assertEqual(c.ctype, GoConnector.ROUTER)
        self.assertEqual(c.router_type, "rb_type_1")
        self.assertEqual(c.router_key, "12345")
        self.assertEqual(c.direction, GoConnector.INBOUND)
        self.assertEqual(str(c), "ROUTER:rb_type_1:12345:INBOUND")

    def test_create_transport_tag_connector_for_model(self):
        c = GoConnector.for_model(FakePlasticChannel("tagpool_1", "tag_1"))
        self.assertEqual(c.ctype, GoConnector.TRANSPORT_TAG)
        self.assertEqual(c.tagpool, "tagpool_1")
        self.assertEqual(c.tagname, "tag_1")
        self.assertEqual(str(c), "TRANSPORT_TAG:tagpool_1:tag_1")
