# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api."""

import uuid

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.helpers import VumiTestCase
from vumi.errors import VumiError

from go.vumitools.opt_out import OptOutStore
from go.vumitools.contact import ContactStore
from go.vumitools.account.old_models import AccountStoreVNone, AccountStoreV1
from go.vumitools.routing_table import GoConnector, RoutingTable
from go.vumitools.tests.helpers import VumiApiHelper
from go.vumitools.api import (
    VumiUserApi, VumiApiCommand, VumiApiEvent, TagpoolSet)


class TestTxVumiApi(VumiTestCase):
    is_sync = False

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(
            VumiApiHelper(is_sync=self.is_sync))
        self.vumi_api = self.vumi_helper.get_vumi_api()

    @inlineCallbacks
    def test_declare_tags_from_different_pools(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolB", "tag2")
        yield self.vumi_api.tpm.declare_tags([tag1, tag2])
        self.assertEqual((yield self.vumi_api.tpm.acquire_tag("poolA")), tag1)
        self.assertEqual((yield self.vumi_api.tpm.acquire_tag("poolB")), tag2)

    @inlineCallbacks
    def test_send_command(self):
        for addr in ["+12", "+34"]:
            yield self.vumi_api.send_command(
                "dummy_worker", "send", batch_id="b123", content="Hello!",
                msg_options={'from_addr': '+56'}, to_addr=addr)

        [cmd1, cmd2] = self.vumi_helper.get_dispatched_commands()
        self.assertEqual(cmd1.payload['kwargs']['to_addr'], '+12')
        self.assertEqual(cmd2.payload['kwargs']['to_addr'], '+34')

    @inlineCallbacks
    def test_tagpool_set(self):
        yield self.vumi_helper.setup_tagpool(u'pool1', [u'1.1'], {
            'display_name': 'Pool 1'
        })

        yield self.vumi_helper.setup_tagpool(u'pool2', [u'1.1'], {
            'display_name': 'Pool 2'
        })

        pools = yield self.vumi_api.tagpool_set([u'pool1', u'pool2'])
        self.assertEqual(sorted(pools.pools()), [u'pool1', u'pool2'])
        self.assertEqual(pools.display_name('pool1'), 'Pool 1')
        self.assertEqual(pools.display_name('pool2'), 'Pool 2')

    @inlineCallbacks
    def test_known_tagpools(self):
        yield self.vumi_helper.setup_tagpool(u'pool1', [u'1.1'])
        yield self.vumi_helper.setup_tagpool(u'pool2', [u'2.1'])
        pools = yield self.vumi_api.known_tagpools()
        self.assertEqual(sorted(pools.pools()), [u'pool1', u'pool2'])


class TestVumiApi(TestTxVumiApi):
    is_sync = True


class TestTxVumiUserApi(VumiTestCase):
    is_sync = False

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(
            VumiApiHelper(is_sync=self.is_sync))
        self.vumi_api = self.vumi_helper.get_vumi_api()
        self.user_helper = yield self.vumi_helper.make_user(u'Buster')
        self.user_api = self.user_helper.user_api

        # Some stores for old versions to test migrations.
        self.account_store_vnone = AccountStoreVNone(self.vumi_api.manager)
        self.account_store_v1 = AccountStoreV1(self.vumi_api.manager)

    def test_create_converts_key_to_unicode(self):
        """
        The user_account_key attr should be unicode even if a bytestring was
        provided.
        """
        user_api_from_unicode = VumiUserApi(self.vumi_api, u'foo')
        self.assertIsInstance(user_api_from_unicode.user_account_key, unicode)
        user_api_from_bytes = VumiUserApi(self.vumi_api, 'foo')
        self.assertIsInstance(user_api_from_bytes.user_account_key, unicode)

    @inlineCallbacks
    def test_optout_filtering(self):
        group = yield self.user_api.contact_store.new_group(u'test-group')
        user_account = yield self.user_helper.get_user_account()
        optout_store = OptOutStore.from_user_account(user_account)
        contact_store = ContactStore.from_user_account(user_account)

        # Create two random contacts
        yield self.user_api.contact_store.new_contact(
            msisdn=u'+27761234567', groups=[group.key])
        yield self.user_api.contact_store.new_contact(
            msisdn=u'+27760000000', groups=[group.key])

        conv = yield self.user_helper.create_conversation(
            u'dummy', delivery_class=u'sms', groups=[group])

        # Opt out the first contact
        yield optout_store.new_opt_out(u'msisdn', u'+27761234567', {
            'message_id': u'the-message-id'
        })
        contact_keys = yield contact_store.get_contacts_for_conversation(conv)
        all_addrs = []
        for contacts in contact_store.contacts.load_all_bunches(contact_keys):
            for contact in (yield contacts):
                all_addrs.append(contact.addr_for(conv.delivery_class))
        self.assertEqual(set(all_addrs), set(['+27760000000', '+27761234567']))
        optedin_addrs = []
        for contacts in (yield conv.get_opted_in_contact_bunches(
                conv.delivery_class)):
            for contact in (yield contacts):
                optedin_addrs.append(contact.addr_for(conv.delivery_class))
        self.assertEqual(optedin_addrs, ['+27760000000'])

    @inlineCallbacks
    def test_exists(self):
        self.assertTrue(
            (yield self.vumi_api.user_exists(self.user_helper.account_key)))
        self.assertTrue((yield self.user_api.exists()))

        self.assertFalse((yield self.vumi_api.user_exists('foo')))
        self.assertFalse((yield VumiUserApi(self.vumi_api, 'foo').exists()))

    @inlineCallbacks
    def test_active_channels(self):
        tag1, tag2, tag3 = yield self.vumi_helper.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"])
        yield self.user_helper.add_tagpool_permission(u"pool1")

        yield self.user_api.acquire_specific_tag(tag1)
        channels = yield self.user_api.active_channels()
        self.assertEqual(
            set(ch.key for ch in channels),
            set(u':'.join(tag) for tag in [tag1]))

        yield self.user_api.acquire_specific_tag(tag2)
        channels = yield self.user_api.active_channels()
        self.assertEqual(
            set(ch.key for ch in channels),
            set(u':'.join(tag) for tag in [tag1, tag2]))

    @inlineCallbacks
    def assert_account_tags(self, expected):
        user_account = yield self.user_api.get_user_account()
        self.assertEqual(expected, user_account.tags)

    @inlineCallbacks
    def test_declare_acquire_and_release_tags(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        yield self.vumi_api.tpm.declare_tags([tag1, tag2])
        yield self.user_helper.add_tagpool_permission(u"poolA")
        yield self.user_helper.add_tagpool_permission(u"poolB")

        yield self.assert_account_tags([])
        tag2_info = yield self.vumi_api.mdb.get_tag_info(tag2)
        self.assertEqual(tag2_info.metadata['user_account'], None)
        self.assertEqual(tag2_info.current_batch.key, None)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), tag1)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), tag2)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), None)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolB")), None)
        yield self.assert_account_tags([list(tag1), list(tag2)])
        tag2_info = yield self.vumi_api.mdb.get_tag_info(tag2)
        self.assertEqual(tag2_info.metadata['user_account'],
                         self.user_api.user_account_key)
        self.assertNotEqual(tag2_info.current_batch.key, None)

        yield self.user_api.release_tag(tag2)
        yield self.assert_account_tags([list(tag1)])
        tag2_info = yield self.vumi_api.mdb.get_tag_info(tag2)
        self.assertEqual(tag2_info.metadata['user_account'], None)
        self.assertEqual(tag2_info.current_batch.key, None)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), tag2)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), None)
        yield self.assert_account_tags([list(tag1), list(tag2)])

    @inlineCallbacks
    def test_release_tag_without_owner(self):
        [tag] = yield self.vumi_helper.setup_tagpool(u"pool1", [u"1234"])
        yield self.user_helper.add_tagpool_permission(u"pool1")
        yield self.user_api.acquire_specific_tag(tag)

        tag_info = yield self.vumi_api.mdb.get_tag_info(tag)
        del tag_info.metadata['user_account']
        yield tag_info.save()

        yield self.assert_account_tags([list(tag)])
        yield self.user_api.release_tag(tag)
        yield self.assert_account_tags([])

    @inlineCallbacks
    def test_batch_id_for_specific_tag(self):
        [tag] = yield self.vumi_helper.setup_tagpool(u"poolA", [u"tag1"])
        yield self.user_helper.add_tagpool_permission(u"poolA")
        yield self.user_api.acquire_specific_tag(tag)
        tag_info = yield self.vumi_api.mdb.get_tag_info(tag)
        self.assertNotEqual(tag_info.current_batch.key, None)

    def _set_routing_table(self, user, entries):
        # Each entry is a tuple of (src, dst) where src and dst are
        # conversations, tags or connector strings.
        routing_table = RoutingTable()
        user.routing_table = routing_table

        def mkconn(thing):
            if isinstance(thing, basestring):
                return GoConnector.parse(thing)
            else:
                # Assume it's a conversation/channel/router.
                return thing.get_connector()

        for src, dst in entries:
            routing_table.add_entry(
                mkconn(src), "default", mkconn(dst), "default")

    @inlineCallbacks
    def test_release_tag_with_routing_entries(self):
        [tag1] = yield self.vumi_helper.setup_tagpool(u"pool1", [u"1234"])
        yield self.user_helper.add_tagpool_permission(u"pool1")
        yield self.assert_account_tags([])
        yield self.user_api.acquire_specific_tag(tag1)
        yield self.assert_account_tags([list(tag1)])

        conv = yield self.user_api.new_conversation(
            u'bulk_message', u'name', u'desc', {})
        channel = yield self.user_api.get_channel(tag1)
        user = yield self.user_api.get_user_account()
        self._set_routing_table(user, [(conv, channel), (channel, conv)])
        yield user.save()

        self.assertNotEqual(
            RoutingTable(), (yield self.user_api.get_routing_table()))
        yield self.user_api.release_tag(tag1)
        yield self.assert_account_tags([])
        self.assertEqual(
            RoutingTable(), (yield self.user_api.get_routing_table()))

    @inlineCallbacks
    def test_get_empty_routing_table(self):
        routing_table = yield self.user_api.get_routing_table()
        self.assertEqual(RoutingTable(), routing_table)

    @inlineCallbacks
    def _setup_routing_table_test_new_conv(self, routing_table=None):
        tag1, tag2, tag3 = yield self.vumi_helper.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"])
        yield self.user_helper.add_tagpool_permission(u"pool1")
        yield self.user_api.acquire_specific_tag(tag1)
        conv = yield self.user_api.new_conversation(
            u'bulk_message', u'name', u'desc', {})
        conv = self.user_api.wrap_conversation(conv)
        # We don't want to actually send commands here.
        conv.dispatch_command = lambda *args, **kw: None
        yield conv.start()

        # Set the status manually, because it's in `starting', not `running'
        conv.set_status_started()
        yield conv.save()

        returnValue(conv)

    @inlineCallbacks
    def test_get_routing_table(self):
        """
        .get_routing_table() returns the correct routing table data.
        """
        conv = yield self._setup_routing_table_test_new_conv()
        channel = yield self.user_api.get_channel((u'pool1', u'1234'))
        user = yield self.user_api.get_user_account()
        self._set_routing_table(user, [(conv, channel), (channel, conv)])
        yield user.save()
        routing_table = yield self.user_api.get_routing_table()
        self.assertEqual(routing_table, RoutingTable({
            u':'.join([u'CONVERSATION:bulk_message', conv.key]): {
                u'default': [u'TRANSPORT_TAG:pool1:1234', u'default']},
            u'TRANSPORT_TAG:pool1:1234': {
                u'default': [
                    u'CONVERSATION:bulk_message:%s' % conv.key, u'default']},
        }))

    @inlineCallbacks
    def test_archived_routing_table(self):
        """
        Archiving a conversation removes routing entries for that conversation.
        """
        conv = yield self._setup_routing_table_test_new_conv()
        channel = yield self.user_api.get_channel((u'pool1', u'1234'))
        user = yield self.user_api.get_user_account()
        self._set_routing_table(user, [(conv, channel), (channel, conv)])
        yield user.save()
        routing_table = yield self.user_api.get_routing_table()
        self.assertNotEqual(routing_table, RoutingTable())

        yield conv.archive_conversation()

        routing_table = yield self.user_api.get_routing_table()
        self.assertEqual(routing_table, RoutingTable())

    @inlineCallbacks
    def test_routing_table_validation_valid(self):
        conv = yield self._setup_routing_table_test_new_conv()
        channel = yield self.user_api.get_channel((u'pool1', u'1234'))
        user = yield self.user_api.get_user_account()
        self._set_routing_table(user, [(conv, channel), (channel, conv)])
        yield user.save()
        yield self.user_api.validate_routing_table(user)

    @inlineCallbacks
    def test_routing_table_invalid_src_conn_tag(self):
        conv = yield self._setup_routing_table_test_new_conv()
        channel = yield self.user_api.get_channel((u'pool1', u'1234'))
        badchannel = yield self.user_api.get_channel((u'badpool', u'bad'))
        user = yield self.user_api.get_user_account()
        self._set_routing_table(user, [(conv, channel), (badchannel, conv)])
        yield user.save()
        try:
            yield self.user_api.validate_routing_table(user)
            self.fail("Expected VumiError, got no exception.")
        except VumiError as e:
            self.assertTrue('badpool:bad' in str(e))

    @inlineCallbacks
    def test_routing_table_invalid_dst_conn_tag(self):
        conv = yield self._setup_routing_table_test_new_conv()
        channel = yield self.user_api.get_channel((u'pool1', u'1234'))
        badchannel = yield self.user_api.get_channel((u'badpool', u'bad'))
        user = yield self.user_api.get_user_account()
        self._set_routing_table(user, [(conv, badchannel), (channel, conv)])
        yield user.save()
        try:
            yield self.user_api.validate_routing_table(user)
            self.fail("Expected VumiError, got no exception.")
        except VumiError as e:
            self.assertTrue('TRANSPORT_TAG:badpool:bad' in str(e))

    @inlineCallbacks
    def test_routing_table_invalid_src_conn_conv(self):
        conv = yield self._setup_routing_table_test_new_conv()
        channel = yield self.user_api.get_channel((u'pool1', u'1234'))
        badconv = 'CONVERSATION:bulk_message:badkey'
        user = yield self.user_api.get_user_account()
        self._set_routing_table(user, [(badconv, channel), (channel, conv)])
        yield user.save()
        try:
            yield self.user_api.validate_routing_table(user)
            self.fail("Expected VumiError, got no exception.")
        except VumiError as e:
            self.assertTrue('CONVERSATION:bulk_message:badkey' in str(e))

    @inlineCallbacks
    def test_routing_table_invalid_dst_conn_conv(self):
        conv = yield self._setup_routing_table_test_new_conv()
        channel = yield self.user_api.get_channel((u'pool1', u'1234'))
        badconv = 'CONVERSATION:bulk_message:badkey'
        user = yield self.user_api.get_user_account()
        self._set_routing_table(user, [(conv, channel), (channel, badconv)])
        yield user.save()
        try:
            yield self.user_api.validate_routing_table(user)
            self.fail("Expected VumiError, got no exception.")
        except VumiError as e:
            self.assertTrue('CONVERSATION:bulk_message:badkey' in str(e))

    @inlineCallbacks
    def add_app_permission(self, application):
        permission = self.user_api.api.account_store.application_permissions(
            uuid.uuid4().hex, application=application)
        yield permission.save()

        account = yield self.user_api.get_user_account()
        account.applications.add(permission)
        yield account.save()

    @inlineCallbacks
    def test_applications(self):
        applications = yield self.user_api.applications()
        self.assertEqual(applications, {})
        yield self.add_app_permission(u'go.apps.bulk_message')
        applications = yield self.user_api.applications()
        self.assertEqual(applications, {
            u'go.apps.bulk_message': {
                'display_name': 'Group Message',
                'namespace': 'bulk_message',
            }})

    @inlineCallbacks
    def test_tagpools(self):
        yield self.vumi_helper.setup_tagpool(u'pool1', [u'1.1'])
        yield self.vumi_helper.setup_tagpool(u'pool2', [u'2.1'])
        yield self.user_helper.add_tagpool_permission(u'pool1')
        yield self.user_helper.add_tagpool_permission(u'pool2')

        pools = yield self.user_api.tagpools()
        self.assertEqual(sorted(pools.pools()), [u'pool1', u'pool2'])

    @inlineCallbacks
    def test_tagpools_max_keys(self):
        yield self.vumi_helper.setup_tagpool(u'pool1', [u'1.1', u'1.2'])
        yield self.user_helper.add_tagpool_permission(u'pool1', max_keys=2)

        pools = yield self.user_api.tagpools()
        self.assertEqual(sorted(pools.pools()), [u'pool1'])

        yield self.user_api.acquire_specific_tag((u'pool1', u'1.1'))
        pools = yield self.user_api.tagpools()
        self.assertEqual(sorted(pools.pools()), [u'pool1'])

        yield self.user_api.acquire_specific_tag((u'pool1', u'1.2'))
        pools = yield self.user_api.tagpools()
        self.assertEqual(pools.pools(), [])

    @inlineCallbacks
    def test_tagpools_available(self):
        user2_helper = yield self.vumi_helper.make_user(u'User 2')
        user2_api = user2_helper.user_api
        yield self.vumi_helper.setup_tagpool(u'pool1', [u'1.1', u'1.2'])
        yield self.user_helper.add_tagpool_permission(u'pool1')
        yield user2_helper.add_tagpool_permission(u'pool1')

        yield user2_api.acquire_specific_tag((u'pool1', u'1.1'))
        pools = yield self.user_api.tagpools()
        self.assertEqual(sorted(pools.pools()), [u'pool1'])

        yield user2_api.acquire_specific_tag((u'pool1', u'1.2'))
        pools = yield self.user_api.tagpools()
        self.assertEqual(pools.pools(), [])

    @inlineCallbacks
    def test_tagpools_accessible(self):
        yield self.vumi_helper.setup_tagpool(u'pool1', [u'1.1'])
        pools = yield self.user_api.tagpools()
        self.assertEqual(pools.pools(), [])


class TestVumiUserApi(TestTxVumiUserApi):
    sync_persistence = True


class TestTxVumiRouterApi(VumiTestCase):
    is_sync = False

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(
            VumiApiHelper(is_sync=self.is_sync))
        self.user_helper = yield self.vumi_helper.make_user(u'Buster')
        self.user_api = self.user_helper.user_api

    def create_router(self, **kw):
        # TODO: Fix test infrastructure to avoid duplicating this stuff.
        router_type = kw.pop('router_type', u'keyword')
        name = kw.pop('name', u'routername')
        description = kw.pop('description', u'')
        config = kw.pop('config', {})
        self.assertTrue(isinstance(config, dict))
        return self.user_api.new_router(
            router_type, name, description, config, **kw)

    @inlineCallbacks
    def get_router_api(self, router=None):
        if router is None:
            router = yield self.create_router()
        returnValue(
            self.user_api.get_router_api(router.router_type, router.key))

    @inlineCallbacks
    def test_get_router(self):
        router = yield self.create_router()
        router_api = yield self.get_router_api(router)
        got_router = yield router_api.get_router()
        self.assertEqual(router.router_type, got_router.router_type)
        self.assertEqual(router.key, got_router.key)
        self.assertEqual(router.name, got_router.name)
        self.assertEqual(router.description, got_router.description)
        self.assertEqual(router.config, got_router.config)

    @inlineCallbacks
    def _add_routing_entries(self, router):
        conv_conn = 'CONVERSATION:type:key'
        tag_conn = 'TRANSPORT_TAG:pool:tag'
        rin_conn = router.get_inbound_connector()
        rout_conn = router.get_outbound_connector()

        user_account = yield self.user_api.get_user_account()
        routing_table = user_account.routing_table
        routing_table.add_entry(tag_conn, 'default', rin_conn, 'default')
        routing_table.add_entry(rin_conn, 'default', tag_conn, 'default')
        routing_table.add_entry(conv_conn, 'default', rout_conn, 'default')
        routing_table.add_entry(rout_conn, 'default', conv_conn, 'default')
        yield user_account.save()

    @inlineCallbacks
    def test_archive_router(self):
        router = yield self.create_router()
        router_api = yield self.get_router_api(router)
        yield self._add_routing_entries(router)
        self.assertEqual(router.archive_status, 'active')
        self.assertNotEqual(
            RoutingTable(), (yield self.user_api.get_routing_table()))

        yield router_api.archive_router()
        router = yield router_api.get_router()
        self.assertEqual(router.archive_status, 'archived')
        self.assertEqual(
            RoutingTable(), (yield self.user_api.get_routing_table()))

    @inlineCallbacks
    def test_start_router(self):
        router = yield self.create_router()
        router_api = yield self.get_router_api(router)
        self.assertTrue(router.stopped())
        self.assertFalse(router.starting())
        self.assertEqual([], self.vumi_helper.get_dispatched_commands())

        yield router_api.start_router()
        router = yield router_api.get_router()
        self.assertFalse(router.stopped())
        self.assertTrue(router.starting())
        [cmd] = self.vumi_helper.get_dispatched_commands()
        self.assertEqual(cmd['command'], 'start')
        self.assertEqual(cmd['kwargs'], {
            'user_account_key': router.user_account.key,
            'router_key': router.key,
        })

    @inlineCallbacks
    def test_stop_router(self):
        router = yield self.create_router(status=u'running')
        router_api = yield self.get_router_api(router)
        self.assertTrue(router.running())
        self.assertFalse(router.stopping())
        self.assertEqual([], self.vumi_helper.get_dispatched_commands())

        yield router_api.stop_router()
        router = yield router_api.get_router()
        self.assertFalse(router.running())
        self.assertTrue(router.stopping())
        [cmd] = self.vumi_helper.get_dispatched_commands()
        self.assertEqual(cmd['command'], 'stop')
        self.assertEqual(cmd['kwargs'], {
            'user_account_key': router.user_account.key,
            'router_key': router.key,
        })


class TestVumiRouterApi(TestTxVumiRouterApi):
    is_sync = True


class TestVumiApiCommand(VumiTestCase):
    def test_command(self):
        cmd = VumiApiCommand.command(
            'worker', 'my_cmd', 'arg1', 'arg2', kw1=1, kw2=2)
        self.assertEqual(cmd['worker_name'], 'worker')
        self.assertEqual(cmd['command'], 'my_cmd')
        self.assertEqual(cmd['args'], ['arg1', 'arg2'])
        self.assertEqual(cmd['kwargs'], {'kw1': 1, 'kw2': 2})

    def test_conversation_command(self):
        cmd = VumiApiCommand.conversation_command(
            'worker', 'my_cmd', 'me', 'conv', 'arg1', 'arg2', kw1=1, kw2=2)
        self.assertEqual(cmd['worker_name'], 'worker')
        self.assertEqual(cmd['command'], 'my_cmd')
        self.assertEqual(cmd['args'], ['arg1', 'arg2'])
        self.assertEqual(cmd['kwargs'], {
            'user_account_key': 'me',
            'conversation_key': 'conv',
            'kw1': 1,
            'kw2': 2,
        })


class TestVumiApiEvent(VumiTestCase):
    def test_event(self):
        event = VumiApiEvent.event(
            'me', 'my_conv', 'my_event', {"foo": "bar"})
        self.assertEqual(event['account_key'], 'me')
        self.assertEqual(event['conversation_key'], 'my_conv')
        self.assertEqual(event['event_type'], 'my_event')
        self.assertEqual(event['content'], {"foo": "bar"})


class TestTagpoolSet(VumiTestCase):
    def test_pools(self):
        pools = TagpoolSet({
            'pool1': {},
            'pool2': {}
        })

        self.assertEqual(sorted(pools.pools()), ['pool1', 'pool2'])

    def test_display_name(self):
        pools = TagpoolSet({
            'pool1': {'display_name': 'Pool 1'},
            'pool2': {'display_name': 'Pool 2'}
        })

        self.assertEqual(pools.display_name('pool1'), 'Pool 1')
        self.assertEqual(pools.display_name('pool2'), 'Pool 2')

    def test_display_name_fallback(self):
        pools = TagpoolSet({
            'pool1': {'display_name': 'Pool 1'},
            'pool2': {}
        })

        self.assertEqual(pools.display_name('pool1'), 'Pool 1')
        self.assertEqual(pools.display_name('pool2'), 'pool2')

    def test_country_name(self):
        pools = TagpoolSet({
            'pool1': {'country_name': 'Foo'},
            'pool2': {'country_name': 'Bar'}
        })

        self.assertEqual(pools.country_name('pool1', None), 'Foo')
        self.assertEqual(pools.country_name('pool2', None), 'Bar')

    def test_country_name_default(self):
        pools = TagpoolSet({
            'pool1': {'country_name': 'Foo'},
            'pool2': {}
        })

        self.assertEqual(pools.country_name('pool1', 'Baz'), 'Foo')
        self.assertEqual(pools.country_name('pool2', 'Bar'), 'Bar')

    def test_user_selects_tag(self):
        pools = TagpoolSet({
            'pool1': {'user_selects_tag': True},
            'pool2': {'user_selects_tag': False}
        })

        self.assertTrue(pools.user_selects_tag('pool1'))
        self.assertFalse(pools.user_selects_tag('pool2'))

    def test_user_selects_tag_fallback(self):
        pools = TagpoolSet({
            'pool1': {'user_selects_tag': True},
            'pool2': {}
        })

        self.assertTrue(pools.user_selects_tag('pool1'))
        self.assertFalse(pools.user_selects_tag('pool2'))

    def test_delivery_class(self):
        pools = TagpoolSet({
            'pool1': {'delivery_class': 'sms'},
            'pool2': {'delivery_class': 'ussd'}
        })

        self.assertEqual(pools.delivery_class('pool1'), 'sms')
        self.assertEqual(pools.delivery_class('pool2'), 'ussd')

    def test_delivery_class_fallback(self):
        pools = TagpoolSet({
            'pool1': {'delivery_class': 'sms'},
            'pool2': {}
        })

        self.assertEqual(pools.delivery_class('pool1'), 'sms')
        self.assertEqual(pools.delivery_class('pool2'), None)

    def test_delivery_classes(self):
        pools = TagpoolSet({
            'pool1': {'delivery_class': 'sms'},
            'pool2': {'delivery_class': 'ussd'},
        })

        self.assertEqual(pools.delivery_classes(), ['sms', 'ussd'])

    def test_delivery_classes_unspecifieds(self):
        pools = TagpoolSet({
            'pool1': {'delivery_class': 'sms'},
            'pool2': {},
        })

        self.assertEqual(pools.delivery_classes(), ['sms'])

    def test_delivery_class_name(self):
        pools = TagpoolSet({})
        self.assertEqual(pools.delivery_class_name('sms'), 'SMS')
        self.assertEqual(pools.delivery_class_name('ussd'), 'USSD')
        self.assertEqual(pools.delivery_class_name('gtalk'), 'Gtalk')
