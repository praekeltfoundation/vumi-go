# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api."""

import json

from twisted.trial.unittest import TestCase

from vumi.message import TransportEvent
from vumi.tests.utils import FakeRedis
from vumi.application.tests.test_base import ApplicationTestCase

from go.vumitools.api import (VumiApi, MessageStore, MessageSender,
                              VumiApiCommand)
from go.vumitools.tests.utils import CeleryTestMixIn


class TestVumiApi(ApplicationTestCase, CeleryTestMixIn):
    # inherits from ApplicationTestCase for .mkmsg_in and .mkmsg_out

    def setUp(self):
        self.setup_celery_for_tests()
        self.api = VumiApi({
            'message_store': {},
            'message_sender': {},
            })
        self.api.mdb.r_server = FakeRedis()

    def tearDown(self):
        self.restore_celery()

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
            self.api.mdb.add_message(batch_id, msg)
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
            self.api.mdb.add_inbound_message(msg)
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


class TestMessageStore(ApplicationTestCase):
    # inherits from ApplicationTestCase for .mkmsg_in and .mkmsg_out

    def setUp(self):
        self.store = MessageStore({})
        self.store.r_server = FakeRedis()

    def tearDown(self):
        self.store.r_server.teardown()

    def test_batch_start(self):
        tag1 = ("poolA", "tag1")
        batch_id = self.store.batch_start([tag1])
        self.assertEqual(self.store.batch_messages(batch_id), [])
        self.assertEqual(self.store.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 0, 'sent': 0,
            })
        self.assertEqual(self.store.batch_common(batch_id),
                         {"tags": [tag1]})
        self.assertEqual(self.store.tag_common(tag1),
                         {"current_batch_id": batch_id})

    def test_declare_tags(self):
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        self.store.declare_tags([tag1, tag2])
        self.assertEqual(self.store.acquire_tag("poolA"), tag1)
        self.assertEqual(self.store.acquire_tag("poolA"), tag2)
        self.assertEqual(self.store.acquire_tag("poolA"), None)
        tag3 = ("poolA", "tag3")
        self.store.declare_tags([tag2, tag3])
        self.assertEqual(self.store.acquire_tag("poolA"), tag3)

    def test_acquire_tag(self):
        tkey = lambda x: "message_store:tagpools:poolA:" + x
        tag1, tag2 = ("poolA", "tag1"), ("poolA", "tag2")
        self.store.declare_tags([tag1, tag2])
        self.assertEqual(self.store.acquire_tag("poolA"), tag1)
        self.assertEqual(self.store.acquire_tag("poolB"), None)
        self.assertEqual(self.store.r_server.lrange(tkey("free:list"),
                                                    0, -1),
                         ["tag2"])
        self.assertEqual(self.store.r_server.smembers(tkey("free:set")),
                         set(["tag2"]))
        self.assertEqual(self.store.r_server.smembers(tkey("inuse:set")),
                         set(["tag1"]))

    def test_release_tag(self):
        tkey = lambda x: "message_store:tagpools:poolA:" + x
        tag1, tag2, tag3 = [("poolA", "tag%d" % i) for i in (1, 2, 3)]
        self.store.declare_tags([tag1, tag2, tag3])
        self.store.acquire_tag("poolA")
        self.store.acquire_tag("poolA")
        self.store.release_tag(tag1)
        self.assertEqual(self.store.r_server.lrange(tkey("free:list"),
                                                    0, -1),
                         ["tag3", "tag1"])
        self.assertEqual(self.store.r_server.smembers(tkey("free:set")),
                         set(["tag1", "tag3"]))
        self.assertEqual(self.store.r_server.smembers(tkey("inuse:set")),
                         set(["tag2"]))

    def test_add_message(self):
        batch_id = self.store.batch_start([("pool", "tag")])
        msg = self.mkmsg_out(content="outfoo")
        msg_id = msg['message_id']
        self.store.add_message(batch_id, msg)

        self.assertEqual(self.store.get_message(msg_id), msg)
        self.assertEqual(self.store.message_batches(msg_id), [batch_id])
        self.assertEqual(self.store.batch_messages(batch_id), [msg_id])
        self.assertEqual(self.store.message_events(msg_id), [])
        self.assertEqual(self.store.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 1, 'sent': 1,
            })

    def test_add_ack_event(self):
        batch_id = self.store.batch_start([("pool", "tag")])
        msg = self.mkmsg_out(content="outfoo")
        msg_id = msg['message_id']
        ack = TransportEvent(user_message_id=msg_id, event_type='ack',
                             sent_message_id='xyz')
        ack_id = ack['event_id']
        self.store.add_message(batch_id, msg)
        self.store.add_event(ack)

        self.assertEqual(self.store.get_event(ack_id), ack)
        self.assertEqual(self.store.message_events(msg_id), [ack_id])

    def test_add_inbound_message(self):
        msg = self.mkmsg_in(content="infoo")
        msg_id = msg['message_id']
        self.store.add_inbound_message(msg)

        self.assertEqual(self.store.get_inbound_message(msg_id), msg)

    def test_add_inbound_message_with_tag(self):
        batch_id = self.store.batch_start([("ambient", "default10001")])
        msg = self.mkmsg_in(content="infoo", to_addr="+1234567810001",
                            transport_type="sms")
        msg_id = msg['message_id']
        self.store.add_inbound_message(msg)

        self.assertEqual(self.store.get_inbound_message(msg_id), msg)
        self.assertEqual(self.store.batch_replies(batch_id), [msg_id])


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
