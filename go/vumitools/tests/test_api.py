# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api."""

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from go.vumitools.opt_out import OptOutStore
from go.vumitools.api import (
    VumiApi, VumiUserApi, MessageSender, VumiApiCommand, VumiApiEvent)
from go.vumitools.tests.utils import AppWorkerTestCase, CeleryTestMixIn


class TestTxVumiApi(AppWorkerTestCase):
    override_dummy_consumer = False

    @inlineCallbacks
    def setUp(self):
        yield super(TestTxVumiApi, self).setUp()
        if self.sync_persistence:
            self.api = VumiApi.from_config(self._persist_config)
        else:
            self.api = yield VumiApi.from_config_async(self._persist_config)
        self._persist_riak_managers.append(self.api.manager)
        self._persist_redis_managers.append(self.api.redis)

    @inlineCallbacks
    def test_batch_start(self):
        tag = ("pool", "tag")
        batch_id = yield self.api.batch_start([tag])
        self.assertEqual(len(batch_id), 32)

    @inlineCallbacks
    def test_batch_status(self):
        tag = ("pool", "tag")
        batch_id = yield self.api.mdb.batch_start([tag])
        batch_status = yield self.api.batch_status(batch_id)
        self.assertEqual(batch_status['sent'], 0)

    @inlineCallbacks
    def test_batch_send(self):
        consumer = self.get_cmd_consumer()
        msg_options = {"from_addr": "+100", "worker_name": "dummy_worker"}
        yield self.api.batch_send("b123", "Hello!", msg_options,
                                  ["+12", "+34", "+56"])
        [cmd1, cmd2, cmd3] = self.fetch_cmds(consumer)
        send_msg = lambda to_addr: VumiApiCommand.send("b123", "Hello!",
                                                       msg_options, to_addr)
        self.assertEqual(cmd1, send_msg("+12"))
        self.assertEqual(cmd2, send_msg("+34"))
        self.assertEqual(cmd3, send_msg("+56"))

    @inlineCallbacks
    def test_batch_messages(self):
        batch_id = yield self.api.batch_start([("poolA", "default10001")])
        msgs = [self.mkmsg_out(content=msg, message_id=str(i)) for
                i, msg in enumerate(("msg1", "msg2"))]
        for msg in msgs:
            yield self.api.mdb.add_outbound_message(msg, batch_id=batch_id)
        api_msgs = yield self.api.batch_messages(batch_id)
        api_msgs.sort(key=lambda msg: msg['message_id'])
        self.assertEqual(api_msgs, msgs)

    @inlineCallbacks
    def test_batch_replies(self):
        tag = ("ambient", "default10001")
        to_addr = "+12310001"
        batch_id = yield self.api.batch_start([tag])
        msgs = [self.mkmsg_in(content=msg, to_addr=to_addr, message_id=str(i),
                              transport_type="sms")
                for i, msg in enumerate(("msg1", "msg2"))]
        for msg in msgs:
            yield self.api.mdb.add_inbound_message(msg, batch_id=batch_id)
        api_msgs = yield self.api.batch_replies(batch_id)
        api_msgs.sort(key=lambda msg: msg['message_id'])
        self.assertEqual(api_msgs, msgs)

    @inlineCallbacks
    def test_batch_tags(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        batch_id = yield self.api.batch_start([tag1])
        self.assertEqual((yield self.api.batch_tags(batch_id)), [tag1])
        batch_id = yield self.api.batch_start([tag1, tag2])
        self.assertEqual((yield self.api.batch_tags(batch_id)), [tag1, tag2])

    @inlineCallbacks
    def test_declare_acquire_and_release_tags(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        yield self.api.declare_tags([tag1, tag2])
        self.assertEqual((yield self.api.acquire_tag("poolA")), tag1)
        self.assertEqual((yield self.api.acquire_tag("poolA")), tag2)
        self.assertEqual((yield self.api.acquire_tag("poolA")), None)
        self.assertEqual((yield self.api.acquire_tag("poolB")), None)

        yield self.api.release_tag(tag2)
        self.assertEqual((yield self.api.acquire_tag("poolA")), tag2)
        self.assertEqual((yield self.api.acquire_tag("poolA")), None)

    @inlineCallbacks
    def test_declare_tags_from_different_pools(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolB", "tag2")
        yield self.api.declare_tags([tag1, tag2])
        self.assertEqual((yield self.api.acquire_tag("poolA")), tag1)
        self.assertEqual((yield self.api.acquire_tag("poolB")), tag2)

    @inlineCallbacks
    def test_start_batch_and_batch_done(self):
        tag = ("pool", "tag")
        yield self.api.declare_tags([tag])

        @inlineCallbacks
        def tag_batch(t):
            tb = yield self.api.mdb.get_tag_info(t)
            if tb is None:
                returnValue(None)
            returnValue(tb.current_batch.key)

        self.assertEqual((yield tag_batch(tag)), None)

        batch_id = yield self.api.batch_start([tag])
        self.assertEqual((yield tag_batch(tag)), batch_id)

        yield self.api.batch_done(batch_id)
        self.assertEqual((yield tag_batch(tag)), None)


class TestVumiApi(TestTxVumiApi):
    sync_persistence = True


class TestTxVumiUserApi(AppWorkerTestCase):
    override_dummy_consumer = False

    @inlineCallbacks
    def setUp(self):
        yield super(TestTxVumiUserApi, self).setUp()
        if self.sync_persistence:
            self.api = VumiApi.from_config(self._persist_config)
        else:
            self.api = yield VumiApi.from_config_async(self._persist_config)
        self.user_account = yield self.api.account_store.new_user(u'Buster')
        self.user_api = VumiUserApi(self.api, self.user_account.key)

    @inlineCallbacks
    def tearDown(self):
        self.restore_celery()
        yield self.api.manager.purge_all()
        yield self.api.redis._purge_all()
        yield self.api.redis.close_manager()

    @inlineCallbacks
    def test_optout_filtering(self):
        group = yield self.user_api.contact_store.new_group(u'test-group')
        optout_store = OptOutStore.from_user_account(self.user_account)

        # Create two random contacts
        yield self.user_api.contact_store.new_contact(
            msisdn=u'+27761234567', groups=[group.key])
        yield self.user_api.contact_store.new_contact(
            msisdn=u'+27760000000', groups=[group.key])

        conv = yield self.user_api.new_conversation(
            u'bulk_message', u'subject', u'message', delivery_class=u'sms')
        conv = self.user_api.wrap_conversation(conv)
        conv.add_group(group)
        yield conv.save()

        # Opt out the first contact
        yield optout_store.new_opt_out(u'msisdn', u'+27761234567', {
            'message_id': u'the-message-id'
        })
        all_addrs = yield conv.get_contacts_addresses()
        self.assertEqual(set(all_addrs), set(['+27760000000', '+27761234567']))
        optedin_addrs = yield conv.get_opted_in_addresses()
        self.assertEqual(optedin_addrs, ['+27760000000'])


class TestVumiUserApi(TestTxVumiUserApi):
    sync_persistence = True


class TestMessageSender(TestCase, CeleryTestMixIn):
    def setUp(self):
        self.setup_celery_for_tests()
        self.mapi = MessageSender({})

    def tearDown(self):
        self.restore_celery()

    def test_batch_send(self):
        consumer = self.get_cmd_consumer()
        msg_options = {"from_addr": "+56", "worker_name": "dummy_worker"}

        for addr in ["+12", "+34"]:
            cmd = VumiApiCommand.command("dummy_worker", "send",
                    batch_id="b123", content="Hello!",
                    msg_options={'from_addr': '+56'}, to_addr=addr)
            self.mapi.send_command(cmd)

        [cmd1, cmd2] = self.fetch_cmds(consumer)
        send_msg = lambda to_addr: VumiApiCommand.send("b123", "Hello!",
                                                       msg_options, to_addr)
        self.assertEqual(cmd1, send_msg("+12"))
        self.assertEqual(cmd2, send_msg("+34"))


class TestVumiApiCommand(TestCase):
    def test_default_routing_config(self):
        cfg = VumiApiCommand.default_routing_config()
        self.assertEqual(set(cfg.keys()),
                         set(['exchange', 'exchange_type', 'routing_key']))

    def test_send(self):
        cmd = VumiApiCommand.send('b123', 'content', {
                "from_addr": "+89",
                "worker_name": "dummy_worker"
            }, '+4567')
        self.assertEqual(cmd['command'], 'send')
        self.assertEqual(cmd['worker_name'], 'dummy_worker')
        self.assertEqual(cmd['kwargs'], {
            'batch_id': 'b123',
            'content': 'content',
            'msg_options': {
                'from_addr': '+89',
            },
            'to_addr': '+4567'
        })


class TestVumiApiEvent(TestCase):
    def test_default_routing_config(self):
        cfg = VumiApiEvent.default_routing_config()
        self.assertEqual(set(cfg.keys()),
                         set(['exchange', 'exchange_type', 'routing_key']))

    def test_event(self):
        event = VumiApiEvent.event(
            'me', 'my_conv', 'my_event', {"foo": "bar"})
        self.assertEqual(event['account_key'], 'me')
        self.assertEqual(event['conversation_key'], 'my_conv')
        self.assertEqual(event['event_type'], 'my_event')
        self.assertEqual(event['content'], {"foo": "bar"})
