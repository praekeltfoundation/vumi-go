# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api."""

from twisted.trial.unittest import TestCase

from vumi.tests.utils import FakeRedis
from vumi.application.tests.test_base import ApplicationTestCase

from go.vumitools.api import VumiApi, MessageSender, VumiApiCommand
from go.vumitools.tests.utils import CeleryTestMixIn


class TestVumiApi(ApplicationTestCase, CeleryTestMixIn):
    # inherits from ApplicationTestCase for .mkmsg_in and .mkmsg_out

    def setUp(self):
        self.setup_celery_for_tests()
        self.r_server = FakeRedis()
        self.api = VumiApi({
            'redis_cls': lambda **config: self.r_server
            })

    def tearDown(self):
        self.restore_celery()
        self.api.manager.purge_all()
        self.r_server.teardown()

    def test_batch_start(self):
        tag = ("pool", "tag")
        batch_id = self.api.batch_start([tag])
        self.assertEqual(len(batch_id), 32)

    def test_batch_status(self):
        tag = ("pool", "tag")
        batch_id = self.api.mdb.batch_start([tag])
        self.assertEqual(self.api.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 0, 'sent': 0,
            })

    def test_batch_send(self):
        consumer = self.get_cmd_consumer()
        msg_options = {"from_addr": "+100"}
        self.api.batch_send("b123", "Hello!", msg_options,
                            ["+12", "+34", "+56"])
        [cmd1, cmd2, cmd3] = self.fetch_cmds(consumer)
        send_msg = lambda to_addr: VumiApiCommand.send("b123", "Hello!",
                                                       msg_options, to_addr)
        self.assertEqual(cmd1, send_msg("+12"))
        self.assertEqual(cmd2, send_msg("+34"))
        self.assertEqual(cmd3, send_msg("+56"))

    def test_batch_messages(self):
        batch_id = self.api.batch_start([("poolA", "default10001")])
        msgs = [self.mkmsg_out(content=msg, message_id=str(i)) for
                i, msg in enumerate(("msg1", "msg2"))]
        for msg in msgs:
            self.api.mdb.add_outbound_message(msg, batch_id=batch_id)
        api_msgs = self.api.batch_messages(batch_id)
        api_msgs.sort(key=lambda msg: msg['message_id'])
        self.assertEqual(api_msgs, msgs)

    def test_batch_replies(self):
        tag = ("ambient", "default10001")
        to_addr = "+12310001"
        batch_id = self.api.batch_start([tag])
        msgs = [self.mkmsg_in(content=msg, to_addr=to_addr, message_id=str(i),
                              transport_type="sms")
                for i, msg in enumerate(("msg1", "msg2"))]
        for msg in msgs:
            self.api.mdb.add_inbound_message(msg, batch_id=batch_id)
        api_msgs = self.api.batch_replies(batch_id)
        api_msgs.sort(key=lambda msg: msg['message_id'])
        self.assertEqual(api_msgs, msgs)

    def test_batch_tags(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        batch_id = self.api.batch_start([tag1])
        self.assertEqual(self.api.batch_tags(batch_id), [tag1])
        batch_id = self.api.batch_start([tag1, tag2])
        self.assertEqual(self.api.batch_tags(batch_id), [tag1, tag2])

    def test_declare_acquire_and_release_tags(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        self.api.declare_tags([tag1, tag2])
        self.assertEqual(self.api.acquire_tag("poolA"), tag1)
        self.assertEqual(self.api.acquire_tag("poolA"), tag2)
        self.assertEqual(self.api.acquire_tag("poolA"), None)
        self.assertEqual(self.api.acquire_tag("poolB"), None)

        self.api.release_tag(tag2)
        self.assertEqual(self.api.acquire_tag("poolA"), tag2)
        self.assertEqual(self.api.acquire_tag("poolA"), None)

    def test_declare_tags_from_different_pools(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolB", "tag2")
        self.api.declare_tags([tag1, tag2])
        self.assertEqual(self.api.acquire_tag("poolA"), tag1)
        self.assertEqual(self.api.acquire_tag("poolB"), tag2)

    def test_start_batch_and_batch_done(self):
        tag = ("pool", "tag")
        self.api.declare_tags([tag])

        tag_batch = lambda t: self.api.mdb.get_tag_info(t).current_batch.key
        self.assertEqual(tag_batch(tag), None)

        batch_id = self.api.batch_start([tag])
        self.assertEqual(tag_batch(tag), batch_id)

        self.api.batch_done(batch_id)
        self.assertEqual(tag_batch(tag), None)


class TestMessageSender(TestCase, CeleryTestMixIn):
    def setUp(self):
        self.setup_celery_for_tests()
        self.mapi = MessageSender({})

    def tearDown(self):
        self.restore_celery()

    def test_batch_send(self):
        consumer = self.get_cmd_consumer()
        msg_options = {"from_addr": "+56"}
        self.mapi.batch_send("b123", "Hello!", msg_options, ["+12", "+34"])
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
        cmd = VumiApiCommand.send('b123', 'content', {"from_addr": "+89"},
                                  '+4567')
        self.assertEqual(cmd['command'], 'send')
        self.assertEqual(cmd['batch_id'], 'b123')
        self.assertEqual(cmd['content'], 'content')
        self.assertEqual(cmd['msg_options'], {"from_addr": "+89"})
        self.assertEqual(cmd['to_addr'], '+4567')
