# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api."""

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.utils import get_fake_amq_client, LogCatcher
from vumi.errors import VumiError

from go.vumitools.opt_out import OptOutStore
from go.vumitools.contact import ContactStore
from go.vumitools.api import (
    VumiApi, VumiUserApi, VumiApiCommand, VumiApiEvent)
from go.vumitools.tests.utils import AppWorkerTestCase, FakeAmqpConnection
from go.vumitools.account.old_models import AccountStoreVNone, AccountStoreV1
from go.vumitools.account.models import GoConnector, RoutingTableHelper


class TestTxVumiApi(AppWorkerTestCase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestTxVumiApi, self).setUp()
        if self.sync_persistence:
            # Set up the vumi exchange, in case we don't have one.
            self._amqp.exchange_declare('vumi', 'direct')
            self.vumi_api = VumiApi.from_config_sync(
                self._persist_config, FakeAmqpConnection(self._amqp))
        else:
            self.vumi_api = yield VumiApi.from_config_async(
                self._persist_config, get_fake_amq_client(self._amqp))
        self._persist_riak_managers.append(self.vumi_api.manager)
        self._persist_redis_managers.append(self.vumi_api.redis)

    @inlineCallbacks
    def test_batch_start(self):
        tag = ("pool", "tag")
        batch_id = yield self.vumi_api.batch_start([tag])
        self.assertEqual(len(batch_id), 32)

    @inlineCallbacks
    def test_batch_status(self):
        tag = ("pool", "tag")
        batch_id = yield self.vumi_api.mdb.batch_start([tag])
        batch_status = yield self.vumi_api.batch_status(batch_id)
        self.assertEqual(batch_status['sent'], 0)

    @inlineCallbacks
    def test_batch_outbound_keys(self):
        batch_id = yield self.vumi_api.batch_start([("poolA", "default10001")])
        msgs = [self.mkmsg_out(content=msg, message_id=str(i)) for
                i, msg in enumerate(("msg1", "msg2"))]
        for msg in msgs:
            yield self.vumi_api.mdb.add_outbound_message(
                msg, batch_id=batch_id)
        api_msgs = yield self.vumi_api.batch_outbound_keys(batch_id)
        self.assertEqual(sorted(api_msgs), ['0', '1'])

    @inlineCallbacks
    def test_batch_inbound_keys(self):
        tag = ("ambient", "default10001")
        to_addr = "+12310001"
        batch_id = yield self.vumi_api.batch_start([tag])
        msgs = [self.mkmsg_in(content=msg, to_addr=to_addr, message_id=str(i),
                              transport_type="sms")
                for i, msg in enumerate(("msg1", "msg2"))]
        for msg in msgs:
            yield self.vumi_api.mdb.add_inbound_message(msg, batch_id=batch_id)
        api_msgs = yield self.vumi_api.batch_inbound_keys(batch_id)
        self.assertEqual(sorted(api_msgs), ['0', '1'])

    @inlineCallbacks
    def test_batch_tags(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        batch_id = yield self.vumi_api.batch_start([tag1])
        self.assertEqual((yield self.vumi_api.batch_tags(batch_id)), [tag1])
        batch_id = yield self.vumi_api.batch_start([tag1, tag2])
        self.assertEqual(
            (yield self.vumi_api.batch_tags(batch_id)), [tag1, tag2])

    @inlineCallbacks
    def test_declare_tags_from_different_pools(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolB", "tag2")
        yield self.vumi_api.tpm.declare_tags([tag1, tag2])
        self.assertEqual((yield self.vumi_api.tpm.acquire_tag("poolA")), tag1)
        self.assertEqual((yield self.vumi_api.tpm.acquire_tag("poolB")), tag2)

    @inlineCallbacks
    def test_start_batch_and_batch_done(self):
        tag = ("pool", "tag")
        yield self.vumi_api.tpm.declare_tags([tag])

        @inlineCallbacks
        def tag_batch(t):
            tb = yield self.vumi_api.mdb.get_tag_info(t)
            if tb is None:
                returnValue(None)
            returnValue(tb.current_batch.key)

        self.assertEqual((yield tag_batch(tag)), None)

        batch_id = yield self.vumi_api.batch_start([tag])
        self.assertEqual((yield tag_batch(tag)), batch_id)

        yield self.vumi_api.batch_done(batch_id)
        self.assertEqual((yield tag_batch(tag)), None)

    @inlineCallbacks
    def test_send_command(self):
        for addr in ["+12", "+34"]:
            yield self.vumi_api.send_command(
                    "dummy_worker", "send",
                    batch_id="b123", content="Hello!",
                    msg_options={'from_addr': '+56'}, to_addr=addr)

        [cmd1, cmd2] = self.get_dispatcher_commands()
        self.assertEqual(cmd1.payload['kwargs']['to_addr'], '+12')
        self.assertEqual(cmd2.payload['kwargs']['to_addr'], '+34')


class TestVumiApi(TestTxVumiApi):
    sync_persistence = True


class TestTxVumiUserApi(AppWorkerTestCase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestTxVumiUserApi, self).setUp()
        if self.sync_persistence:
            self.vumi_api = VumiApi.from_config_sync(self._persist_config)
        else:
            self.vumi_api = yield VumiApi.from_config_async(
                self._persist_config)
        self.user_account = yield self.mk_user(self.vumi_api, u'Buster')
        self.user_api = VumiUserApi(self.vumi_api, self.user_account.key)

        # Some stores for old versions to test migrations.
        self.account_store_vnone = AccountStoreVNone(self.vumi_api.manager)
        self.account_store_v1 = AccountStoreV1(self.vumi_api.manager)

    @inlineCallbacks
    def test_optout_filtering(self):
        group = yield self.user_api.contact_store.new_group(u'test-group')
        optout_store = OptOutStore.from_user_account(self.user_account)
        contact_store = ContactStore.from_user_account(self.user_account)

        # Create two random contacts
        yield self.user_api.contact_store.new_contact(
            msisdn=u'+27761234567', groups=[group.key])
        yield self.user_api.contact_store.new_contact(
            msisdn=u'+27760000000', groups=[group.key])

        conv = yield self.create_conversation(
            conversation_type=u'dummy', delivery_class=u'sms')
        conv.add_group(group)
        yield conv.save()

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
        for contacts in (yield conv.get_opted_in_contact_bunches()):
            for contact in (yield contacts):
                optedin_addrs.append(contact.addr_for(conv.delivery_class))
        self.assertEqual(optedin_addrs, ['+27760000000'])

    @inlineCallbacks
    def test_exists(self):
        self.assertTrue(
            (yield self.vumi_api.user_exists(self.user_account.key)))
        self.assertTrue((yield self.user_api.exists()))

        self.assertFalse((yield self.vumi_api.user_exists('foo')))
        self.assertFalse((yield VumiUserApi(self.vumi_api, 'foo').exists()))

    @inlineCallbacks
    def test_list_conversation_endpoints(self):
        tag1, tag2, tag3 = yield self.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"])
        yield self.user_api.acquire_specific_tag(tag2)
        yield self.user_api.new_conversation(
            u'bulk_message', u'name', u'desc', {}, delivery_class=u'sms',
            delivery_tag_pool=tag1[0], delivery_tag=tag1[1])
        endpoints = yield self.user_api.list_conversation_endpoints()
        self.assertEqual(endpoints, set([tag1]))

    @inlineCallbacks
    def test_list_endpoints(self):
        tag1, tag2, tag3 = yield self.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"])
        yield self.user_api.acquire_specific_tag(tag1)
        endpoints = yield self.user_api.list_endpoints()
        self.assertEqual(endpoints, set([tag1]))

    @inlineCallbacks
    def test_list_endpoints_migration(self):
        tag1, tag2, tag3 = yield self.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"])
        yield self.user_api.acquire_specific_tag(tag1)
        conv = yield self.user_api.new_conversation(
            u'bulk_message', u'name', u'desc', {}, delivery_class=u'sms',
            delivery_tag_pool=tag1[0], delivery_tag=tag1[1])
        conv = self.user_api.wrap_conversation(conv)
        # We don't want to actually send commands here.
        conv.dispatch_command = lambda *args, **kw: None
        yield conv.start(acquire_tag=False)

        self.assertEqual(tag1, (conv.delivery_tag_pool, conv.delivery_tag))
        conv_endpoints = yield self.user_api.list_conversation_endpoints()
        self.assertEqual(conv_endpoints, set([tag1]))

        # Pretend this is an old-style account that was migrated.
        user = yield self.user_api.get_user_account()
        user.tags = None
        yield user.save()

        endpoints = yield self.user_api.list_endpoints()
        self.assertEqual(endpoints, set([tag1]))

    @inlineCallbacks
    def test_msg_options(self):
        tag1, tag2, tag3 = yield self.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"])
        yield self.vumi_api.tpm.set_metadata(u"pool1", {
            'transport_type': 'dummy_transport',
            'msg_options': {'opt1': 'bar'},
        })
        msg_options = yield self.user_api.msg_options(tag1)
        self.assertEqual(msg_options, {
            'from_addr': '1234',
            'helper_metadata': {
                'go': {'user_account': 'test-0-user'},
                'tag': {'tag': ['pool1', '1234']},
            },
            'transport_type': 'dummy_transport',
            'opt1': 'bar',
        })

    @inlineCallbacks
    def test_msg_options_with_tagpool_metadata(self):
        tag = ('pool1', '1234')
        tagpool_metadata = {
            'transport_type': 'dummy_transport',
            'msg_options': {'opt1': 'bar'},
        }
        msg_options = yield self.user_api.msg_options(tag, tagpool_metadata)
        self.assertEqual(msg_options, {
            'from_addr': '1234',
            'helper_metadata': {
                'go': {'user_account': 'test-0-user'},
                'tag': {'tag': ['pool1', '1234']},
            },
            'transport_type': 'dummy_transport',
            'opt1': 'bar',
        })

    @inlineCallbacks
    def assert_account_tags(self, expected):
        user_account = yield self.user_api.get_user_account()
        self.assertEqual(expected, user_account.tags)

    @inlineCallbacks
    def test_declare_acquire_and_release_tags(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        yield self.vumi_api.tpm.declare_tags([tag1, tag2])
        yield self.add_tagpool_permission(u"poolA")
        yield self.add_tagpool_permission(u"poolB")

        yield self.assert_account_tags([])
        tag2_info = yield self.vumi_api.mdb.get_tag_info(tag2)
        self.assertEqual(tag2_info.metadata['user_account'], None)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), tag1)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), tag2)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), None)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolB")), None)
        yield self.assert_account_tags([list(tag1), list(tag2)])
        tag2_info = yield self.vumi_api.mdb.get_tag_info(tag2)
        self.assertEqual(tag2_info.metadata['user_account'],
                         self.user_api.user_account_key)

        yield self.user_api.release_tag(tag2)
        yield self.assert_account_tags([list(tag1)])
        tag2_info = yield self.vumi_api.mdb.get_tag_info(tag2)
        self.assertEqual(tag2_info.metadata['user_account'], None)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), tag2)
        self.assertEqual((yield self.user_api.acquire_tag(u"poolA")), None)
        yield self.assert_account_tags([list(tag1), list(tag2)])

    @inlineCallbacks
    def test_release_tag_with_routing_entries(self):
        [tag1] = yield self.setup_tagpool(u"pool1", [u"1234"])
        yield self.assert_account_tags([])
        yield self.user_api.acquire_specific_tag(tag1)
        yield self.assert_account_tags([list(tag1)])

        conv = yield self.user_api.new_conversation(
            u'bulk_message', u'name', u'desc', {})
        user = yield self.user_api.get_user_account()
        rt_helper = RoutingTableHelper(user.routing_table)

        tag_conn = str(GoConnector.for_transport_tag(tag1[0], tag1[1]))
        conv_conn = str(
            GoConnector.for_conversation(conv.conversation_type, conv.key))
        rt_helper.add_entry(conv_conn, "default", tag_conn, "default")
        rt_helper.add_entry(tag_conn, "default", conv_conn, "default")
        yield user.save()

        self.assertNotEqual({}, (yield self.user_api.get_routing_table()))
        yield self.user_api.release_tag(tag1)
        yield self.assert_account_tags([])
        self.assertEqual({}, (yield self.user_api.get_routing_table()))

    @inlineCallbacks
    def test_get_empty_routing_table(self):
        routing_table = yield self.user_api.get_routing_table()
        self.assertEqual({}, routing_table)

    @inlineCallbacks
    def _setup_routing_table_test_conv(self):
        tag1, tag2, tag3 = yield self.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"])
        yield self.user_api.acquire_specific_tag(tag1)
        conv = yield self.user_api.new_conversation(
            u'bulk_message', u'name', u'desc', {}, delivery_class=u'sms',
            delivery_tag_pool=tag2[0], delivery_tag=tag2[1])
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
        conv = yield self._setup_routing_table_test_conv()
        routing_table = yield self.user_api.get_routing_table()
        self.assertEqual(routing_table, {
            u':'.join([u'CONVERSATION:bulk_message', conv.key]): {
                u'default': [u'TRANSPORT_TAG:pool1:5678', u'default']},
            u'TRANSPORT_TAG:pool1:5678': {
                u'default': [
                    u'CONVERSATION:bulk_message:%s' % conv.key, u'default']},
        })

        # TODO: This belongs in a different test.
        yield conv.end_conversation()

        routing_table = yield self.user_api.get_routing_table()
        self.assertEqual(routing_table, {})

    @inlineCallbacks
    def test_get_routing_table_migration(self):
        conv = yield self._setup_routing_table_test_conv()
        # Pretend this is an old-style account that was migrated.
        user = yield self.user_api.get_user_account()
        user.routing_table = None
        yield user.save()

        with LogCatcher(message=r'No routing configured') as lc:
            routing_table = yield self.user_api.get_routing_table()
        self.assertEqual(lc.messages(), [])
        self.assertEqual(routing_table, {
            u':'.join(['CONVERSATION:bulk_message', conv.key]): {
                'default': [u'TRANSPORT_TAG:pool1:5678', u'default']},
            u'TRANSPORT_TAG:pool1:5678': {
                u'default': [
                    u':'.join(['CONVERSATION:bulk_message', conv.key]),
                    'default'
                ],
            },
        })

    @inlineCallbacks
    def test_get_routing_table_migration_missing_entry(self):
        conv = yield self._setup_routing_table_test_conv()
        conv2 = yield self.user_api.new_conversation(
            u'bulk_message', u'name', u'desc', {}, delivery_class=u'sms',
            delivery_tag_pool=u'pool1', delivery_tag=u'9012')
        conv2 = self.user_api.wrap_conversation(conv2)
        # We don't want to actually send commands here.
        conv2.dispatch_command = lambda *args, **kw: None
        yield conv2.start()

        # Set the status manually, because it's in `starting', not `running'
        conv2.set_status_started()
        yield conv2.save()

        # Release the tag, but keep the conv running.
        yield self.user_api.release_tag((u'pool1', u'9012'))

        # Pretend this is an old-style account that was migrated.
        user = yield self.user_api.get_user_account()
        user.routing_table = None
        yield user.save()

        with LogCatcher(message=r'No routing configured') as lc:
            routing_table = yield self.user_api.get_routing_table()
        self.assertEqual(len(lc.messages()), 1)
        self.assertTrue(conv2.key in lc.messages()[0])
        self.assertEqual(routing_table, {
            u':'.join(['CONVERSATION:bulk_message', conv.key]): {
                'default': [u'TRANSPORT_TAG:pool1:5678', u'default']},
            u'TRANSPORT_TAG:pool1:5678': {
                u'default': [
                    u':'.join(['CONVERSATION:bulk_message', conv.key]),
                    'default'
                ],
            },
        })

    @inlineCallbacks
    def test_routing_table_validation_valid(self):
        yield self._setup_routing_table_test_conv()
        user = yield self.user_api.get_user_account()
        yield self.user_api.validate_routing_table(user)

    @inlineCallbacks
    def test_routing_table_invalid_src_conn_tag(self):
        conv = yield self._setup_routing_table_test_conv()
        user = yield self.user_api.get_user_account()
        user.routing_table = {
            u':'.join(['CONVERSATION:bulk_message', conv.key]): {
                'default': [u'TRANSPORT_TAG:pool1:5678', u'default']},
            u'TRANSPORT_TAG:badpool:bad': {
                u'default': [
                    u':'.join(['CONVERSATION:bulk_message', conv.key]),
                    'default'
                ],
            },
        }
        try:
            yield self.user_api.validate_routing_table(user)
            self.fail("Expected VumiError, got no exception.")
        except VumiError as e:
            self.assertTrue('badpool:bad' in str(e))

    @inlineCallbacks
    def test_routing_table_invalid_dst_conn_tag(self):
        conv = yield self._setup_routing_table_test_conv()
        user = yield self.user_api.get_user_account()
        user.routing_table = {
            u':'.join(['CONVERSATION:bulk_message', conv.key]): {
                'default': [u'TRANSPORT_TAG:badpool:bad', u'default']},
            u'TRANSPORT_TAG:pool1:5678': {
                u'default': [
                    u':'.join(['CONVERSATION:bulk_message', conv.key]),
                    'default'
                ],
            },
        }
        try:
            yield self.user_api.validate_routing_table(user)
            self.fail("Expected VumiError, got no exception.")
        except VumiError as e:
            self.assertTrue('TRANSPORT_TAG:badpool:bad' in str(e))

    @inlineCallbacks
    def test_routing_table_invalid_src_conn_conv(self):
        conv = yield self._setup_routing_table_test_conv()
        user = yield self.user_api.get_user_account()
        user.routing_table = {
            u'CONVERSATION:bulk_message:badkey': {
                'default': [u'TRANSPORT_TAG:pool1:5678', u'default']},
            u'TRANSPORT_TAG:pool1:5678': {
                u'default': [
                    u':'.join(['CONVERSATION:bulk_message', conv.key]),
                    'default'
                ],
            },
        }
        try:
            yield self.user_api.validate_routing_table(user)
            self.fail("Expected VumiError, got no exception.")
        except VumiError as e:
            self.assertTrue('CONVERSATION:bulk_message:badkey' in str(e))

    @inlineCallbacks
    def test_routing_table_invalid_dst_conn_conv(self):
        conv = yield self._setup_routing_table_test_conv()
        user = yield self.user_api.get_user_account()
        user.routing_table = {
            u':'.join(['CONVERSATION:bulk_message', conv.key]): {
                'default': [u'TRANSPORT_TAG:pool1:5678', u'default']},
            u'TRANSPORT_TAG:pool1:5678': {
                u'default': [u'CONVERSATION:bulk_message:badkey', 'default'],
            },
        }
        try:
            yield self.user_api.validate_routing_table(user)
            self.fail("Expected VumiError, got no exception.")
        except VumiError as e:
            self.assertTrue('CONVERSATION:bulk_message:badkey' in str(e))


class TestVumiUserApi(TestTxVumiUserApi):
    sync_persistence = True


class TestVumiApiCommand(TestCase):
    def test_default_routing_config(self):
        cfg = VumiApiCommand.default_routing_config()
        self.assertEqual(cfg, {
            'exchange': 'vumi',
            'exchange_type': 'direct',
            'routing_key': 'vumi.api',
            'durable': True,
            })


class TestVumiApiEvent(TestCase):
    def test_default_routing_config(self):
        cfg = VumiApiEvent.default_routing_config()
        self.assertEqual(cfg, {
            'exchange': 'vumi',
            'exchange_type': 'direct',
            'routing_key': 'vumi.event',
            'durable': True,
            })

    def test_event(self):
        event = VumiApiEvent.event(
            'me', 'my_conv', 'my_event', {"foo": "bar"})
        self.assertEqual(event['account_key'], 'me')
        self.assertEqual(event['conversation_key'], 'my_conv')
        self.assertEqual(event['event_type'], 'my_event')
        self.assertEqual(event['content'], {"foo": "bar"})
