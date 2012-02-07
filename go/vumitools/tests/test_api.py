# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api."""

from twisted.trial.unittest import TestCase

from vumi.message import TransportEvent
from vumi.tests.utils import FakeRedis
from vumi.application.tests.test_base import ApplicationTestCase

from go.vumitools.api import (VumiApi, MessageStore, MessageSender,
                              VumiApiCommand)
from go.vumitools.tests.utils import CeleryTestMixIn


class TestVumiApi(TestCase, CeleryTestMixIn):
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
        batch_id = self.api.batch_start("tag")
        self.assertEqual(len(batch_id), 32)

    def test_batch_status(self):
        batch_id = self.api.mdb.batch_start("tag")
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


class TestMessageStore(ApplicationTestCase):
    # inherits from ApplicationTestCase for .mkmsg_in and .mkmsg_out

    def setUp(self):
        self.store = MessageStore({})
        self.store.r_server = FakeRedis()

    def tearDown(self):
        self.store.r_server.teardown()

    def test_batch_start(self):
        batch_id = self.store.batch_start("tag1")
        self.assertEqual(self.store.batch_messages(batch_id), [])
        self.assertEqual(self.store.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 0, 'sent': 0,
            })
        self.assertEqual(self.store.batch_common(batch_id),
                         {"tag": "tag1"})
        self.assertEqual(self.store.tag_common("tag1"),
                         {"current_batch_id": batch_id})

    def test_add_message(self):
        batch_id = self.store.batch_start("tag")
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
        batch_id = self.store.batch_start("tag")
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
        batch_id = self.store.batch_start("default10001")
        msg = self.mkmsg_in(content="infoo", from_addr="+1234567810001")
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
