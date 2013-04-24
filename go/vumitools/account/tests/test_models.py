from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase
from vumi.tests.utils import UTCNearNow

from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.account.models import (
    AccountStore, GoConnector, GoConnectorError)
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


class GoConnectorTestCase(TestCase):
    def test_create_conversation_connector(self):
        c = GoConnector.for_conversation("conv_type_1", "12345")
        self.assertEqual(c.ctype, GoConnector.CONVERSATION)
        self.assertEqual(c.conv_type, "conv_type_1")
        self.assertEqual(c.conv_key, "12345")
        self.assertEqual(str(c), "CONVERSATION:conv_type_1:12345")

    def test_create_routing_block_connector(self):
        c = GoConnector.for_routing_block("rb_type_1", "12345")
        self.assertEqual(c.ctype, GoConnector.ROUTING_BLOCK)
        self.assertEqual(c.rblock_type, "rb_type_1")
        self.assertEqual(c.rblock_key, "12345")
        self.assertEqual(str(c), "ROUTING_BLOCK:rb_type_1:12345")

    def test_create_transport_tag_connector(self):
        c = GoConnector.for_transport_tag("tagpool_1", "tag_1")
        self.assertEqual(c.ctype, GoConnector.TRANSPORT_TAG)
        self.assertEqual(c.tagpool, "tagpool_1")
        self.assertEqual(c.tagname, "tag_1")
        self.assertEqual(str(c), "TRANSPORT_TAG:tagpool_1:tag_1")

    def test_parse_conversation_connector(self):
        c = GoConnector.parse("CONVERSATION:conv_type_1:12345")
        self.assertEqual(c.ctype, GoConnector.CONVERSATION)
        self.assertEqual(c.conv_type, "conv_type_1")
        self.assertEqual(c.conv_key, "12345")

    def test_parse_routing_block_connector(self):
        c = GoConnector.parse("ROUTING_BLOCK:rb_type_1:12345")
        self.assertEqual(c.ctype, GoConnector.ROUTING_BLOCK)
        self.assertEqual(c.rblock_type, "rb_type_1")
        self.assertEqual(c.rblock_key, "12345")

    def test_parse_transport_tag_connector(self):
        c = GoConnector.parse("TRANSPORT_TAG:tagpool_1:tag_1")
        self.assertEqual(c.ctype, GoConnector.TRANSPORT_TAG)
        self.assertEqual(c.tagpool, "tagpool_1")
        self.assertEqual(c.tagname, "tag_1")

    def test_parse_unknown_ctype(self):
        self.assertRaises(GoConnectorError, GoConnector.parse,
                          "FOO:tagpool:tag")

    def test_parse_bad_parts(self):
        self.assertRaises(GoConnectorError, GoConnector.parse,
                          "CONVERSATION:foo")  # one part
        self.assertRaises(GoConnectorError, GoConnector.parse,
                          "CONVERSATION:foo:bar:baz")  # three parts
