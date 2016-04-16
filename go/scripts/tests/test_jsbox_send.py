import json
from StringIO import StringIO
from tempfile import NamedTemporaryFile

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import Clock
from twisted.python import usage
from vumi.tests.helpers import VumiTestCase

from go.scripts.jsbox_send import (
    JsBoxSendWorker, JsBoxSendOptions, ScriptError, Ticker)
from go.vumitools.tests.helpers import VumiApiHelper, GoMessageHelper


class TestJsBoxSendOptions(VumiTestCase):

    DEFAULT_ARGS = (
        "--vumigo-config", "default.yaml",
        "--user-account-key", "user-123",
        "--conversation-key", "conv-456",
    )

    def mk_opts(self, args, add_defaults=True):
        args.extend(self.DEFAULT_ARGS)
        opts = JsBoxSendOptions()
        opts.parseOptions(args)
        return opts

    def test_hz_default(self):
        opts = self.mk_opts([])
        self.assertEqual(opts['hz'], 60.0)

    def test_hz_override(self):
        opts = self.mk_opts(["--hz", '10.0'])
        self.assertEqual(opts['hz'], 10.0)

    def test_hz_negative_or_zero(self):
        self.assertRaises(
            usage.UsageError,
            self.mk_opts, ["--hz", "-5.0"])

    def test_hz_not_numeric(self):
        self.assertRaises(
            usage.UsageError,
            self.mk_opts, ["--hz", "foo"])


class TestTicker(VumiTestCase):
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

    @inlineCallbacks
    def get_worker(self):
        vumigo_config = self.vumi_helper.mk_config({})
        worker_helper = self.vumi_helper.get_worker_helper()
        worker = yield worker_helper.get_worker(JsBoxSendWorker, vumigo_config)
        worker.stdout = StringIO()
        returnValue(worker)

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
    def test_get_delivery_class_jsbox(self):
        conv = yield self.user_helper.create_conversation(
            u'jsbox',
            config={
                'jsbox_app_config': {
                    'config': {
                        'key': 'config',
                        'value': json.dumps({
                            'delivery_class': 'twitter',
                        })
                    },
                },
            })
        worker = yield self.get_worker()
        self.assertEqual(worker.get_delivery_class(conv), 'twitter')

    @inlineCallbacks
    def test_get_delivery_class_dialogue(self):
        conv = yield self.user_helper.create_conversation(
            u'dialogue',
            config={
                'poll': {
                    'poll_metadata': {
                        'delivery_class': 'mxit',
                    },
                },
            })
        worker = yield self.get_worker()
        self.assertEqual(worker.get_delivery_class(conv), 'mxit')

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
        self.assertEqual(worker.stdout.getvalue(), '')
        yield worker.send_inbound_push_trigger('+27831234567', conv, 'cont')
        self.assertEqual(
            worker.stdout.getvalue(),
            "Starting u'My Conversation' [%s] -> +27831234567\n" % (conv.key,))
        [msg] = worker_helper.get_dispatched_inbound()
        self.assertEqual(msg['inbound_push_trigger'], True)
        self.assertEqual(msg['from_addr'], '+27831234567')
        self.assertEqual(msg['helper_metadata']['go']['contact_key'], 'cont')

    @inlineCallbacks
    def test_get_excluded_addrs_no_file(self):
        worker = yield self.get_worker()
        excluded_addrs = worker.get_excluded_addrs(None)
        self.assertEqual(excluded_addrs, set())

    @inlineCallbacks
    def test_get_excluded_addrs_simple(self):
        exclude_file = NamedTemporaryFile()
        exclude_file.write('addr1\naddr2')
        exclude_file.flush()

        worker = yield self.get_worker()
        excluded_addrs = worker.get_excluded_addrs(exclude_file.name)
        self.assertEqual(excluded_addrs, set(['addr1', 'addr2']))

    @inlineCallbacks
    def test_get_excluded_addrs_messy(self):
        exclude_file = NamedTemporaryFile()
        exclude_file.write('addr1  \naddr2\n\naddr1\n\taddr3\n')
        exclude_file.flush()

        worker = yield self.get_worker()
        excluded_addrs = worker.get_excluded_addrs(exclude_file.name)
        self.assertEqual(excluded_addrs, set(['addr1', 'addr2', 'addr3']))

    @inlineCallbacks
    def test_get_contacts_for_addrs_no_groups(self):
        conv = yield self.user_helper.create_conversation(u'jsbox')
        worker = yield self.get_worker()
        addrs = yield worker.get_contact_addrs_for_conv(conv, None, set())
        self.assertEqual(addrs, [])
        self.assertEqual(worker.stdout.getvalue(), '')

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
        addrs = yield worker.get_contact_addrs_for_conv(conv, None, set())
        self.assertEqual(
            sorted(addrs), sorted([(c.msisdn, c.key) for c in contacts]))
        self.assertEqual(worker.stdout.getvalue(), 'Addresses collected: 3\n')

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
        addrs = yield worker.get_contact_addrs_for_conv(conv, 'gtalk', set())
        self.assertEqual(
            sorted(addrs), sorted([(c.gtalk_id, c.key) for c in contacts]))

    @inlineCallbacks
    def test_get_contacts_for_addrs_exclude_list(self):
        cs = self.user_helper.user_api.contact_store
        grp = yield cs.new_group(u'group')
        c1 = yield cs.new_contact(msisdn=u'+01', groups=[grp])
        yield cs.new_contact(msisdn=u'+02', groups=[grp])
        c3 = yield cs.new_contact(msisdn=u'+03', groups=[grp])
        conv = yield self.user_helper.create_conversation(
            u'jsbox', groups=[grp])
        worker = yield self.get_worker()
        excluded = set(['+02', '+04'])
        addrs = yield worker.get_contact_addrs_for_conv(conv, None, excluded)
        self.assertEqual(sorted(addrs), [('+01', c1.key), ('+03', c3.key)])
        self.assertEqual(worker.stdout.getvalue(), 'Addresses collected: 2\n')

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

    @inlineCallbacks
    def test_send_jsbox_big_group(self):
        conv = yield self.user_helper.create_conversation(u'jsbox')
        worker = yield self.get_worker()

        def generate_contact_addrs(conv, delivery_class, excluded_addrs):
            return [('+27831234%03s' % i, ('contact-%s' % i))
                    for i in xrange(1000)]

        worker.get_contact_addrs_for_conv = generate_contact_addrs
        worker.send_inbound_push_trigger = lambda *args: None

        yield worker.send_jsbox(self.user_helper.account_key, conv.key, 1000)
        self.assertEqual(worker.stdout.getvalue(), ''.join([
            'Messages sent: 100 / 1000\n',
            'Messages sent: 200 / 1000\n',
            'Messages sent: 300 / 1000\n',
            'Messages sent: 400 / 1000\n',
            'Messages sent: 500 / 1000\n',
            'Messages sent: 600 / 1000\n',
            'Messages sent: 700 / 1000\n',
            'Messages sent: 800 / 1000\n',
            'Messages sent: 900 / 1000\n',
            'Messages sent: 1000 / 1000\n',
        ]))
