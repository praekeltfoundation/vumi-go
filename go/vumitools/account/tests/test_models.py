import copy

import mock

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase
from vumi.tests.utils import UTCNearNow, LogCatcher

from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.account.models import (
    AccountStore, RoutingTableHelper, GoConnector, GoConnectorError)
from go.vumitools.account.old_models import AccountStoreVNone, AccountStoreV1


class UserAccountTestCase(GoPersistenceMixin, TestCase):
    use_riak = True

    def setUp(self):
        self._persist_setUp()
        self.manager = self.get_riak_manager()
        self.store = AccountStore(self.manager)

        # Some old stores for testing migrations.
        self.store_v1 = AccountStoreV1(self.manager)
        self.store_vnone = AccountStoreVNone(self.manager)

    def tearDown(self):
        return self._persist_tearDown()

    def assert_user(self, user, **fields):
        def assert_field(value, name, default):
            self.assertEqual(fields.get(name, default), value, name)

        assert_field(user.username, 'username', u'testuser')
        assert_field(user.tagpools.keys(), 'tagpools', [])
        assert_field(user.applications.keys(), 'applications', [])
        assert_field(user.created_at, 'created_at', UTCNearNow())
        assert_field(user.event_handler_config, 'event_handler_config', [])
        assert_field(user.msisdn, 'msisdn', None)
        assert_field(user.confirm_start_conversation,
                     'confirm_start_conversation', False)
        assert_field(user.tags, 'tags', [])
        assert_field(user.routing_table, 'routing_table', {})

    def assert_user_v1(self, user, **fields):
        def assert_field(value, name, default):
            self.assertEqual(fields.get(name, default), value, name)

        assert_field(user.username, 'username', u'testuser')
        assert_field(user.tagpools.keys(), 'tagpools', [])
        assert_field(user.applications.keys(), 'applications', [])
        assert_field(user.created_at, 'created_at', UTCNearNow())
        assert_field(user.event_handler_config, 'event_handler_config', [])
        assert_field(user.msisdn, 'msisdn', None)
        assert_field(user.confirm_start_conversation,
                     'confirm_start_conversation', False)
        assert_field(user.tags, 'tags', [])

    def assert_user_vnone(self, user, **fields):
        def assert_field(value, name, default):
            self.assertEqual(fields.get(name, default), value, name)

        assert_field(user.username, 'username', u'testuser')
        assert_field(user.tagpools.keys(), 'tagpools', [])
        assert_field(user.applications.keys(), 'applications', [])
        assert_field(user.created_at, 'created_at', UTCNearNow())
        assert_field(user.event_handler_config, 'event_handler_config', None)
        assert_field(user.msisdn, 'msisdn', None)
        assert_field(user.confirm_start_conversation,
                     'confirm_start_conversation', False)

    @inlineCallbacks
    def test_new_account(self):
        user = yield self.store.new_user(u'testuser')
        self.assert_user(user)

    @inlineCallbacks
    def test_migrate_new_from_v1(self):
        user_v1 = yield self.store_v1.new_user(u'testuser')
        self.assert_user_v1(user_v1)
        user = yield self.store.get_user(user_v1.key)
        self.assert_user(user, routing_table=None)

    @inlineCallbacks
    def test_migrate_new_from_vnone(self):
        user_vnone = yield self.store_vnone.new_user(u'testuser')
        self.assert_user_vnone(user_vnone)
        user = yield self.store.get_user(user_vnone.key)
        self.assert_user(user, tags=None, routing_table=None)


class RoutingTableHelperTestCase(TestCase):

    CONV_1 = "CONVERSATION:dummy:1"
    CONV_2 = "CONVERSATION:dummy:2"
    CHANNEL_2 = "TRANSPORT_TAG:pool:tag2"
    CHANNEL_3 = "TRANSPORT_TAG:pool:tag3"
    ROUTER_1_INBOUND = "ROUTING_BLOCK:dummy:1:INBOUND"
    ROUTER_1_OUTBOUND = "ROUTING_BLOCK:dummy:1:OUTBOUND"

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

    def mk_helper(self, routing_table=None):
        if routing_table is None:
            routing_table = copy.deepcopy(self.DEFAULT_ROUTING)
        return RoutingTableHelper(routing_table)

    def test_lookup_target(self):
        rt = self.mk_helper()
        self.assertEqual(rt.lookup_target(self.CONV_1, "default1.1"),
                         [self.CHANNEL_2, "default2"])
        self.assertEqual(rt.lookup_target(self.CONV_1, "default1.2"),
                         [self.CHANNEL_3, "default3"])

    def test_lookup_unknown_target(self):
        rt = self.mk_helper()
        self.assertEqual(rt.lookup_target(self.CHANNEL_3, "default3"),
                         None)

    def test_lookup_source(self):
        rt = self.mk_helper()
        self.assertEqual(rt.lookup_source(self.CHANNEL_2, "default2"),
                         [self.CONV_1, "default1.1"])
        self.assertEqual(rt.lookup_source(self.CHANNEL_3, "default3"),
                         [self.CONV_1, "default1.2"])

    def test_lookup_unknown_source(self):
        rt = self.mk_helper()
        self.assertEqual(rt.lookup_source(self.CONV_1, "default1.1"),
                         None)

    def test_lookup_targets(self):
        rt = self.mk_helper()
        self.assertEqual(
            sorted(rt.lookup_targets(self.CONV_1)),
            [
                ("default1.1", [self.CHANNEL_2, "default2"]),
                ("default1.2", [self.CHANNEL_3, "default3"]),
            ],
        )

    def test_lookup_sources(self):
        rt = self.mk_helper()
        self.assertEqual(
            sorted(rt.lookup_sources(self.CHANNEL_3)),
            [
                ("default3", [self.CONV_1, "default1.2"]),
            ],
        )

    def test_entries(self):
        rt = self.mk_helper()
        self.assertEqual(sorted(rt.entries()), [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_add_entry(self):
        rt = self.mk_helper()
        rt.add_entry("new_conn", "default4", "conn4", "default5")
        self.assertEqual(sorted(rt.entries()), [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
            ("new_conn", "default4", "conn4", "default5"),
        ])

    def test_add_entry_that_exists(self):
        rt = self.mk_helper()
        with LogCatcher() as lc:
            rt.add_entry(self.CONV_1, "default1.2", "conn4", "default4")
            self.assertEqual(lc.messages(), [
                "Replacing routing entry for ('%s', 'default1.2'):"
                " was ['%s', 'default3'], now ['conn4', 'default4']" % (
                    self.CONV_1, self.CHANNEL_3)
            ])
        self.assertEqual(sorted(rt.entries()), [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", "conn4", "default4"),
        ])

    def test_remove_entry(self):
        rt = self.mk_helper()
        rt.remove_entry(self.CONV_1, "default1.1")
        self.assertEqual(sorted(rt.entries()), [
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_remove_entry_that_does_not_exist(self):
        rt = self.mk_helper()
        with LogCatcher() as lc:
            rt.remove_entry(self.CONV_1, "default1.unknown")
            self.assertEqual(lc.messages(), [
                "Attempting to remove missing routing entry for"
                " ('%s', 'default1.unknown')." % (self.CONV_1,)
            ])
        self.assertEqual(sorted(rt.entries()), [
            (self.CONV_1, "default1.1", self.CHANNEL_2, "default2"),
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_remove_connector_source(self):
        rt = self.mk_helper()
        rt.remove_connector(self.CONV_1)
        self.assertEqual(sorted(rt.entries()), [])

    def test_remove_connector_destination(self):
        rt = self.mk_helper()
        rt.remove_connector(self.CHANNEL_2)
        self.assertEqual(sorted(rt.entries()), [
            (self.CONV_1, "default1.2", self.CHANNEL_3, "default3"),
        ])

    def test_remove_conversation(self):
        rt = self.mk_helper({})
        conv = mock.Mock(conversation_type="conv_type_1", key="12345")
        rt.add_entry(
            str(GoConnector.for_conversation(
                conv.conversation_type, conv.key)),
            "default", "TRANSPORT_TAG:pool:tag1", "default2")
        rt.remove_conversation(conv)
        self.assertEqual(sorted(rt.entries()), [])

    def test_remove_transport_tag(self):
        tag = ["pool1", "tag1"]
        rt = self.mk_helper({})
        rt.add_entry(str(GoConnector.for_transport_tag(*tag)),
                     "default", "TRANSPORT_TAG:pool:tag1", "default2")
        rt.remove_transport_tag(tag)
        self.assertEqual(sorted(rt.entries()), [])

    def test_add_oldstyle_conversation(self):
        rt = self.mk_helper({})
        conv = mock.Mock(conversation_type="conv_type_1", key="12345")
        tag = ["pool1", "tag1"]
        rt.add_oldstyle_conversation(conv, tag)
        self.assertEqual(sorted(rt.entries()), [
            ('CONVERSATION:conv_type_1:12345', 'default',
             'TRANSPORT_TAG:pool1:tag1', 'default'),
            ('TRANSPORT_TAG:pool1:tag1', 'default',
             'CONVERSATION:conv_type_1:12345', 'default'),
        ])

    def test_add_oldstyle_conversation_outbound_only(self):
        rt = self.mk_helper({})
        conv = mock.Mock(conversation_type="conv_type_1", key="12345")
        tag = ["pool1", "tag1"]
        rt.add_oldstyle_conversation(conv, tag, outbound_only=True)
        self.assertEqual(sorted(rt.entries()), [
            ('CONVERSATION:conv_type_1:12345', 'default',
             'TRANSPORT_TAG:pool1:tag1', 'default'),
        ])

    def test_transitive_targets_simple_case(self):
        rt = self.mk_helper()
        self.assertEqual(sorted(rt.transitive_targets(self.CONV_1)), [
            self.CHANNEL_2, self.CHANNEL_3,
        ])

    def test_transitive_targets_with_routers(self):
        rt = self.mk_helper(self.COMPLEX_ROUTING)
        self.assertEqual(sorted(rt.transitive_targets(self.CHANNEL_2)), [
            self.CONV_1, self.CONV_2, self.ROUTER_1_INBOUND,
        ])
        self.assertEqual(sorted(rt.transitive_targets(self.CHANNEL_3)), [
        ])
        self.assertEqual(sorted(rt.transitive_targets(self.CONV_1)), [
            self.ROUTER_1_OUTBOUND, self.CHANNEL_2,
        ])
        self.assertEqual(sorted(rt.transitive_targets(self.CONV_2)), [
            self.ROUTER_1_OUTBOUND, self.CHANNEL_2, self.CHANNEL_3,
        ])
        self.assertEqual(sorted(rt.transitive_targets(self.ROUTER_1_INBOUND)),
                         [self.CHANNEL_2])
        self.assertEqual(sorted(rt.transitive_targets(self.ROUTER_1_OUTBOUND)),
                         [self.CONV_1, self.CONV_2])

    def test_transitive_sources_simple_case(self):
        rt = self.mk_helper()
        self.assertEqual(sorted(rt.transitive_sources(self.CHANNEL_2)), [
            self.CONV_1,
        ])

    def test_transitive_sources_with_routers(self):
        rt = self.mk_helper(self.COMPLEX_ROUTING)
        self.assertEqual(sorted(rt.transitive_sources(self.CHANNEL_2)), [
            self.CONV_1, self.CONV_2, self.ROUTER_1_INBOUND,
        ])
        self.assertEqual(sorted(rt.transitive_sources(self.CHANNEL_3)), [
            self.CONV_2,
        ])
        self.assertEqual(sorted(rt.transitive_sources(self.CONV_1)), [
            self.ROUTER_1_OUTBOUND, self.CHANNEL_2,
        ])
        self.assertEqual(sorted(rt.transitive_sources(self.CONV_2)), [
            self.ROUTER_1_OUTBOUND, self.CHANNEL_2,
        ])
        self.assertEqual(sorted(rt.transitive_sources(self.ROUTER_1_INBOUND)),
                         [self.CHANNEL_2])
        self.assertEqual(sorted(rt.transitive_sources(self.ROUTER_1_OUTBOUND)),
                         [self.CONV_1, self.CONV_2])


class GoConnectorTestCase(TestCase):
    def test_create_conversation_connector(self):
        c = GoConnector.for_conversation("conv_type_1", "12345")
        self.assertEqual(c.ctype, GoConnector.CONVERSATION)
        self.assertEqual(c.conv_type, "conv_type_1")
        self.assertEqual(c.conv_key, "12345")
        self.assertEqual(str(c), "CONVERSATION:conv_type_1:12345")

    def test_create_routing_block_connector(self):
        c = GoConnector.for_routing_block("rb_type_1", "12345",
                                          GoConnector.INBOUND)
        self.assertEqual(c.ctype, GoConnector.ROUTING_BLOCK)
        self.assertEqual(c.rblock_type, "rb_type_1")
        self.assertEqual(c.rblock_key, "12345")
        self.assertEqual(c.direction, GoConnector.INBOUND)
        self.assertEqual(str(c), "ROUTING_BLOCK:rb_type_1:12345:INBOUND")

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

    def test_parse_routing_block_connector(self):
        c = GoConnector.parse("ROUTING_BLOCK:rb_type_1:12345:OUTBOUND")
        self.assertEqual(c.ctype, GoConnector.ROUTING_BLOCK)
        self.assertEqual(c.rblock_type, "rb_type_1")
        self.assertEqual(c.rblock_key, "12345")
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

    def test_flip_routing_block_connector(self):
        c1 = GoConnector.for_routing_block(
            "dummy", "1", GoConnector.INBOUND)
        c2 = c1.flip_direction()
        self.assertEqual(c2.direction, GoConnector.OUTBOUND)
        self.assertEqual(c2.ctype, GoConnector.ROUTING_BLOCK)
        self.assertEqual(c2.rblock_type, "dummy")
        self.assertEqual(c2.rblock_key, "1")
        c3 = c2.flip_direction()
        self.assertEqual(c3.direction, GoConnector.INBOUND)

    def test_flip_non_routing_block_connector(self):
        c = GoConnector.for_conversation("dummy", "1")
        self.assertRaises(GoConnectorError, c.flip_direction)
