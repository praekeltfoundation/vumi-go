from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase, PersistenceHelper
from vumi.tests.utils import UTCNearNow

from go.vumitools.account.models import UserAccount, AccountStore, flag_property
from go.vumitools.account.old_models import (
    AccountStoreVNone, AccountStoreV1, AccountStoreV2,
    AccountStoreV4, AccountStoreV5)
from go.vumitools.routing_table import RoutingTable


class TestUserAccountMigrations(VumiTestCase):

    def setUp(self):
        self.persistence_helper = self.add_helper(
            PersistenceHelper(use_riak=True))
        riak_manager = self.persistence_helper.get_riak_manager()
        self.store = AccountStore(riak_manager)

        # Some old stores for testing migrations.
        self.store_v5 = AccountStoreV5(riak_manager)
        self.store_v4 = AccountStoreV4(riak_manager)
        self.store_v2 = AccountStoreV2(riak_manager)
        self.store_v1 = AccountStoreV1(riak_manager)
        self.store_vnone = AccountStoreVNone(riak_manager)

    def store_user_version(self, version):
        # Configure the manager to save the older message version.
        modelcls = self.store.users._modelcls
        model_name = "%s.%s" % (modelcls.__module__, modelcls.__name__)
        self.store.manager.store_versions[model_name] = version

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
        assert_field(user.email_summary, 'email_summary', None)
        assert_field(user.tags, 'tags', [])
        assert_field(set(user.flags), 'flags', set())
        assert_field(user.routing_table, 'routing_table', RoutingTable({}))

    def assert_user_v5(self, user, **fields):
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
        assert_field(user.can_manage_optouts, 'can_manage_optouts', False)
        assert_field(user.disable_optouts, 'disable_optouts', False)
        assert_field(user.email_summary, 'email_summary', None)
        assert_field(user.tags, 'tags', [])
        assert_field(user.routing_table, 'routing_table', RoutingTable({}))

    def assert_user_v4(self, user, **fields):
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
        assert_field(user.can_manage_optouts, 'can_manage_optouts', False)
        assert_field(user.email_summary, 'email_summary', None)
        assert_field(user.tags, 'tags', [])
        assert_field(user.routing_table, 'routing_table', RoutingTable({}))

    def assert_user_v2(self, user, **fields):
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
    def test_migrate_new_from_v2(self):
        user_v2 = yield self.store_v2.new_user(u'testuser')
        self.assert_user_v2(user_v2)
        user = yield self.store.get_user(user_v2.key)
        self.assert_user(user)

    @inlineCallbacks
    def test_migrate_new_from_v1(self):
        user_v1 = yield self.store_v1.new_user(u'testuser')
        self.assert_user_v1(user_v1)
        user = yield self.store.get_user(user_v1.key)
        self.assert_user(user)

    @inlineCallbacks
    def test_migrate_new_from_vnone(self):
        user_vnone = yield self.store_vnone.new_user(u'testuser')
        self.assert_user_vnone(user_vnone)
        user = yield self.store.get_user(user_vnone.key)
        self.assert_user(user)

    @inlineCallbacks
    def test_migrate_new_from_4(self):
        """
        A v4 model can be migrated to the current model version.
        """
        user_v4 = yield self.store_v4.new_user(u'testuser')
        self.assert_user_v4(user_v4)
        user = yield self.store.get_user(user_v4.key)
        self.assert_user(user)

    @inlineCallbacks
    def test_reverse_4_from_new(self):
        """
        The current model version can be migrated to a v4 model.
        """
        user = yield self.store.new_user(u'testuser')
        self.assert_user(user)

        self.store_user_version(4)
        yield user.save()

        user_v4 = yield self.store_v4.get_user(user.key)
        self.assert_user_v4(user_v4)

    @inlineCallbacks
    def test_migrate_new_from_5(self):
        """
        A v5 model can be migrated to the current model version.
        """
        user_v5 = yield self.store_v5.new_user(u'testuser')
        self.assert_user_v5(user_v5)
        user = yield self.store.get_user(user_v5.key)
        self.assert_user(user)

    @inlineCallbacks
    def test_reverse_5_from_new(self):
        """
        The current model version can be migrated to a v5 model.
        """
        user = yield self.store.new_user(u'testuser')
        self.assert_user(user)

        self.store_user_version(5)
        yield user.save()

        user_v5 = yield self.store_v5.get_user(user.key)
        self.assert_user_v5(user_v5)

    @inlineCallbacks
    def test_migrate_new_from_5_disable_optouts(self):
        """
        A v5 model can be migrated to the current model version.
        """
        user_v5 = yield self.store_v5.new_user(u'testuser')
        user_v5.disable_optouts = True
        yield user_v5.save()

        user = yield self.store.get_user(user_v5.key)
        self.assertTrue(u'disable_optouts' in user.flags)

    @inlineCallbacks
    def test_migrate_new_from_5_can_manage_optouts(self):
        """
        A v5 model can be migrated to the current model version.
        """
        user_v5 = yield self.store_v5.new_user(u'testuser')
        user_v5.can_manage_optouts = True
        yield user_v5.save()

        user = yield self.store.get_user(user_v5.key)
        self.assertTrue(u'can_manage_optouts' in user.flags)

    @inlineCallbacks
    def test_reverse_5_from_new_disable_optouts(self):
        """
        The current model version can be migrated to a v5 model.
        """
        user = yield self.store.new_user(u'testuser')
        user.flags.add(u'disable_optouts')
        yield user.save()

        self.store_user_version(5)
        yield user.save()

        user_v5 = yield self.store_v5.get_user(user.key)
        self.assertTrue(user_v5.disable_optouts)

    @inlineCallbacks
    def test_reverse_5_from_new_can_manage_optouts(self):
        """
        The current model version can be migrated to a v5 model.
        """
        user = yield self.store.new_user(u'testuser')
        user.flags.add(u'can_manage_optouts')

        self.store_user_version(5)
        yield user.save()

        user_v5 = yield self.store_v5.get_user(user.key)
        self.assertTrue(user_v5.can_manage_optouts)


class ToyUserAccount(UserAccount):
    foo = flag_property(u'foo')


class TestFlagProperty(VumiTestCase):
    def setUp(self):
        self.persistence_helper = self.add_helper(
            PersistenceHelper(use_riak=True))
        self.manager = self.persistence_helper.get_riak_manager()

    def test_getter(self):
        """
        Determining whether a flag exists should be possible.
        """
        model = self.manager.proxy(ToyUserAccount)
        user = model('123', username=u'testuser')

        self.assertFalse(user.foo)
        user.flags.add(u'foo')
        self.assertTrue(user.foo)
        user.flags.remove(u'foo')
        self.assertFalse(user.foo)

    def test_setter(self):
        """
        Setting and unsetting a flag should be possible.
        """
        model = self.manager.proxy(ToyUserAccount)
        user = model('123', username=u'testuser')

        self.assertFalse(u'foo' in user.flags)
        user.foo = True
        self.assertTrue(u'foo' in user.flags)
        user.foo = False
        self.assertFalse(u'foo' in user.flags)
        user.foo = False
        self.assertFalse(u'foo' in user.flags)
