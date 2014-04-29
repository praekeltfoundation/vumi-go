import json

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock
from vumi.tests.helpers import VumiTestCase

from go.scripts.jsbox_send import JsBoxSendWorker, ScriptError, Ticker
from go.vumitools.tests.helpers import VumiApiHelper, GoMessageHelper


class TestTickjer(VumiTestCase):
    def setUp(self):
        self.override_ticker_clock()

    def override_ticker_clock(self):
        orig_clock = Ticker.clock

        def restore_clock():
            Ticker.clock = orig_clock

        Ticker.clock = Clock()
        self.add_cleanup(restore_clock)

    def test_first_tick(self):
        t = Ticker(hz=1)

        d1 = t.tick()
        self.assertFalse(d1.called)
        t.clock.advance(0)
        self.assertTrue(d1.called)

    def test_fast(self):
        t = Ticker(hz=1)

        t.tick()
        t.clock.advance(0.1)

        d = t.tick()
        self.assertFalse(d.called)
        t.clock.advance(0.5)
        self.assertFalse(d.called)
        t.clock.advance(0.5)
        self.assertTrue(d.called)

    def test_slow(self):
        t = Ticker(hz=1)

        t.tick()
        t.clock.advance(1.5)

        d = t.tick()
        self.assertFalse(d.called)
        t.clock.advance(0)
        self.assertTrue(d.called)


class TestJsBoxSend(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.get_or_create_user()
        self.msg_helper = yield self.add_helper(
            GoMessageHelper(self.vumi_helper))

    def get_worker(self):
        vumigo_config = self.vumi_helper.mk_config({})
        worker_helper = self.vumi_helper.get_worker_helper()
        return worker_helper.get_worker(JsBoxSendWorker, vumigo_config)

    @inlineCallbacks
    def test_get_conversation_jsbox(self):
        conv = yield self.user_helper.create_conversation(u'jsbox')
        worker = yield self.get_worker()
        loaded_conv = yield worker.get_conversation(
            self.user_helper.account_key, conv.key)
        self.assertEqual(conv.key, loaded_conv.key)

    @inlineCallbacks
    def test_get_conversation_dialogue(self):
        conv = yield self.user_helper.create_conversation(u'dialogue')
        worker = yield self.get_worker()
        loaded_conv = yield worker.get_conversation(
            self.user_helper.account_key, conv.key)
        self.assertEqual(conv.key, loaded_conv.key)

    @inlineCallbacks
    def test_get_conversation_unsupported_type(self):
        conv = yield self.user_helper.create_conversation(u'bulk_send')
        worker = yield self.get_worker()
        failure = yield self.assertFailure(worker.get_conversation(
            self.user_helper.account_key, conv.key), ScriptError)
        self.assertEqual(
            str(failure), "Unsupported conversation type: bulk_send")

    @inlineCallbacks
    def test_get_conversation_missing(self):
        worker = yield self.get_worker()
        failure = yield self.assertFailure(worker.get_conversation(
            self.user_helper.account_key, u'badkey'), ScriptError)
        self.assertEqual(str(failure), "Conversation not found: badkey")

    @inlineCallbacks
    def test_send_to_conv_jsbox(self):
        conv = yield self.user_helper.create_conversation(u'jsbox')
        worker = yield self.get_worker()
        worker_helper = self.vumi_helper.get_worker_helper('jsbox_transport')
        msg = self.msg_helper.make_inbound('foo')
        self.assertEqual(worker_helper.get_dispatched_inbound(), [])
        worker.send_to_conv(conv, msg)
        self.assertEqual(worker_helper.get_dispatched_inbound(), [msg])

    @inlineCallbacks
    def test_send_to_conv_dialogue(self):
        conv = yield self.user_helper.create_conversation(u'dialogue')
        worker = yield self.get_worker()
        worker_helper = self.vumi_helper.get_worker_helper(
            'dialogue_transport')
        msg = self.msg_helper.make_inbound('foo')
        self.assertEqual(worker_helper.get_dispatched_inbound(), [])
        worker.send_to_conv(conv, msg)
        self.assertEqual(worker_helper.get_dispatched_inbound(), [msg])

    @inlineCallbacks
    def test_send_inbound_push_trigger(self):
        conv = yield self.user_helper.create_conversation(u'jsbox')
        worker = yield self.get_worker()
        worker_helper = self.vumi_helper.get_worker_helper('jsbox_transport')

        self.assertEqual(worker_helper.get_dispatched_inbound(), [])
        yield worker.send_inbound_push_trigger('+27831234567', conv)
        [msg] = worker_helper.get_dispatched_inbound()
        self.assertEqual(msg['inbound_push_trigger'], True)
        self.assertEqual(msg['from_addr'], '+27831234567')

    @inlineCallbacks
    def test_get_contacts_for_addrs_no_groups(self):
        conv = yield self.user_helper.create_conversation(u'jsbox')
        worker = yield self.get_worker()
        contact_addrs = yield worker.get_contact_addrs_for_conv(conv, None)
        self.assertEqual(contact_addrs, [])

    @inlineCallbacks
    def test_get_contacts_for_addrs_small_group(self):
        cs = self.user_helper.user_api.contact_store
        grp = yield cs.new_group(u'group')
        contacts = [
            (yield cs.new_contact(msisdn=u'+01', groups=[grp])),
            (yield cs.new_contact(msisdn=u'+02', groups=[grp])),
            (yield cs.new_contact(msisdn=u'+03', groups=[grp])),
        ]
        conv = yield self.user_helper.create_conversation(
            u'jsbox', groups=[grp])
        worker = yield self.get_worker()
        contact_addrs = yield worker.get_contact_addrs_for_conv(conv, None)
        self.assertEqual(
            sorted(contact_addrs), sorted([c.msisdn for c in contacts]))

    @inlineCallbacks
    def test_get_contacts_for_addrs_gtalk(self):
        cs = self.user_helper.user_api.contact_store
        grp = yield cs.new_group(u'group')
        contacts = [
            (yield cs.new_contact(msisdn=u'', gtalk_id=u'1@a', groups=[grp])),
            (yield cs.new_contact(msisdn=u'', gtalk_id=u'2@a', groups=[grp])),
            (yield cs.new_contact(msisdn=u'', gtalk_id=u'3@a', groups=[grp])),
        ]
        conv = yield self.user_helper.create_conversation(
            u'jsbox', groups=[grp])
        worker = yield self.get_worker()
        contact_addrs = yield worker.get_contact_addrs_for_conv(conv, 'gtalk')
        self.assertEqual(
            sorted(contact_addrs), sorted([c.gtalk_id for c in contacts]))

    @inlineCallbacks
    def test_send_jsbox_default_delivery_class(self):
        cs = self.user_helper.user_api.contact_store
        grp = yield cs.new_group(u'group')
        contacts = [
            (yield cs.new_contact(msisdn=u'+01', groups=[grp])),
            (yield cs.new_contact(msisdn=u'+02', groups=[grp])),
            (yield cs.new_contact(msisdn=u'+03', groups=[grp])),
        ]
        conv = yield self.user_helper.create_conversation(
            u'jsbox', groups=[grp])
        worker = yield self.get_worker()
        worker_helper = self.vumi_helper.get_worker_helper('jsbox_transport')

        self.assertEqual(worker_helper.get_dispatched_inbound(), [])
        yield worker.send_jsbox(self.user_helper.account_key, conv.key)

        msgs = worker_helper.get_dispatched_inbound()
        msg_addrs = sorted(msg['from_addr'] for msg in msgs)
        self.assertEqual(msg_addrs, [c.msisdn for c in contacts])
        self.assertTrue(all(msg['inbound_push_trigger'] for msg in msgs))

    @inlineCallbacks
    def test_send_jsbox_gtalk(self):
        cs = self.user_helper.user_api.contact_store
        grp = yield cs.new_group(u'group')
        contacts = [
            (yield cs.new_contact(msisdn=u'', gtalk_id=u'1@a', groups=[grp])),
            (yield cs.new_contact(msisdn=u'', gtalk_id=u'2@a', groups=[grp])),
            (yield cs.new_contact(msisdn=u'', gtalk_id=u'3@a', groups=[grp])),
        ]
        conv = yield self.user_helper.create_conversation(
            u'jsbox', groups=[grp], config={'jsbox_app_config': {'config': {
                'key': 'config',
                'value': json.dumps({'delivery_class': 'gtalk'}),
            }}})
        worker = yield self.get_worker()
        worker_helper = self.vumi_helper.get_worker_helper('jsbox_transport')

        self.assertEqual(worker_helper.get_dispatched_inbound(), [])
        yield worker.send_jsbox(self.user_helper.account_key, conv.key)

        msgs = worker_helper.get_dispatched_inbound()
        msg_addrs = sorted(msg['from_addr'] for msg in msgs)
        self.assertEqual(msg_addrs, [c.gtalk_id for c in contacts])
        self.assertTrue(all(msg['inbound_push_trigger'] for msg in msgs))
