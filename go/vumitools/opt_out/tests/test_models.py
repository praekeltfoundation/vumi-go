"""Tests for go.vumitools.opt_out.models."""

from datetime import datetime, timedelta

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportUserMessage

from go.vumitools.tests.utils import GoTestCase
from go.vumitools.account import AccountStore
from go.vumitools.opt_out.models import OptOutStore


class TestOptOutStore(GoTestCase):

    use_riak = True

    @inlineCallbacks
    def setUp(self):
        super(TestOptOutStore, self).setUp()
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        self.account = yield self.mk_user(self, u'user')
        self.opt_out_store = OptOutStore.from_user_account(self.account)

    def mkmsg_in(self, **kw):
        # TODO: replace all these copies of mkmsg_in with a single helper
        opts = {
            'content': 'hello world', 'to_addr': '12345', 'from_addr': '67890',
            'transport_name': 'dummy_transport', 'transport_type': 'dummy',
        }
        opts.update(kw)
        msg = TransportUserMessage(**opts)
        return msg

    def test_setup_proxies(self):
        self.assertTrue(hasattr(self.opt_out_store, 'opt_outs'))
        self.assertEqual(self.opt_out_store.opt_outs.bucket, 'optout')

    def test_opt_out_id(self):
        self.assertEqual(self.opt_out_store.opt_out_id("msisdn", "+1234"),
                         "msisdn:+1234")

    @inlineCallbacks
    def test_new_opt_out(self):
        msg = self.mkmsg_in(content="STOP")
        opt_out = yield self.opt_out_store.new_opt_out(
            "msisdn", "+1234", msg)
        # check opt out is correct
        self.assertEqual(opt_out.key,
                         self.opt_out_store.opt_out_id("msisdn", "+1234"))
        self.assertEqual(opt_out.user_account.key, self.account.key)
        self.assertEqual(opt_out.message, msg['message_id'])
        self.assertTrue(datetime.utcnow() - opt_out.created_at
                        < timedelta(minutes=1))
        # check that opt out was saved
        opt_out_2 = yield self.opt_out_store.opt_outs.load(opt_out.key)
        self.assertEqual(opt_out_2.message, unicode(msg['message_id']))

    @inlineCallbacks
    def test_get_opt_out(self):
        msg = self.mkmsg_in()
        opt_out = yield self.opt_out_store.get_opt_out("msisdn", "+1234")
        self.assertEqual(opt_out, None)
        yield self.opt_out_store.new_opt_out("msisdn", "+1234", msg)
        opt_out = yield self.opt_out_store.get_opt_out("msisdn", "+1234")
        self.assertEqual(opt_out.message, msg['message_id'])

    @inlineCallbacks
    def test_delete_opt_out(self):
        store = self.opt_out_store
        yield store.new_opt_out(
            "msisdn", "+1234", self.mkmsg_in())
        self.assertNotEqual((yield store.get_opt_out("msisdn", "+1234")),
                            None)
        yield store.delete_opt_out("msisdn", "+1234")
        self.assertEqual((yield store.get_opt_out("msisdn", "+1234")),
                         None)

    @inlineCallbacks
    def test_delete_opt_out_that_doesnt_exist(self):
        yield self.opt_out_store.delete_opt_out("msisdn", "+1234")

    @inlineCallbacks
    def test_list_opt_outs(self):
        addrs = [("msisdn", str(i)) for i in range(5)]
        for addr_type, addr in addrs:
            yield self.opt_out_store.new_opt_out(
                addr_type, addr, self.mkmsg_in())
        keys = sorted((yield self.opt_out_store.list_opt_outs()))
        expected_keys = sorted(self.opt_out_store.opt_out_id(addr_type, addr)
                               for addr_type, addr in addrs)
        self.assertEqual(keys, expected_keys)

    @inlineCallbacks
    def test_list_opt_outs_empty(self):
        opt_outs = yield self.opt_out_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

    @inlineCallbacks
    def test_opt_outs_for_addresses(self):
        addrs = [("msisdn", str(i)) for i in range(5)]
        for addr_type, addr in addrs:
            yield self.opt_out_store.new_opt_out(
                addr_type, addr, self.mkmsg_in())
        self.assertEqual(
            sorted((yield self.opt_out_store.opt_outs_for_addresses(
                "msisdn", ["0", "2", "3"]))),
            [self.opt_out_store.opt_out_id("msisdn", str(i))
             for i in (0, 2, 3)])

    @inlineCallbacks
    def test_opt_outs_for_addresses_with_no_addresses(self):
        opt_outs = yield self.opt_out_store.opt_outs_for_addresses(
            "msisdn", [])
        self.assertEqual(opt_outs, [])
