# -*- encoding: utf-8 -*-

"""Tests for go.vumitools.opt_out.models."""

from datetime import datetime, timedelta

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.opt_out.models import OptOutStore
from go.vumitools.tests.helpers import GoMessageHelper, VumiApiHelper


class TestOptOutStore(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        user_account = yield self.user_helper.get_user_account()
        self.opt_out_store = OptOutStore.from_user_account(user_account)
        self.msg_helper = self.add_helper(GoMessageHelper())

    def test_setup_proxies(self):
        self.assertTrue(hasattr(self.opt_out_store, 'opt_outs'))
        self.assertEqual(self.opt_out_store.opt_outs.bucket, 'optout')

    def test_opt_out_id(self):
        self.assertEqual(self.opt_out_store.opt_out_id("msisdn", "+1234"),
                         "msisdn:+1234")

    def test_opt_out_id_with_unicode(self):
        self.assertEqual(self.opt_out_store.opt_out_id("mxit", u"foö"),
                         u"mxit:foö".encode('utf-8'))

    @inlineCallbacks
    def test_new_opt_out(self):
        msg = self.msg_helper.make_inbound("STOP")
        opt_out = yield self.opt_out_store.new_opt_out(
            "msisdn", "+1234", msg)
        # check opt out is correct
        self.assertEqual(opt_out.key,
                         self.opt_out_store.opt_out_id("msisdn", "+1234"))
        self.assertEqual(
            opt_out.user_account.key, self.user_helper.account_key)
        self.assertEqual(opt_out.message, msg['message_id'])
        self.assertTrue(
            datetime.utcnow() - opt_out.created_at < timedelta(minutes=1))
        # check that opt out was saved
        opt_out_2 = yield self.opt_out_store.opt_outs.load(opt_out.key)
        self.assertEqual(opt_out_2.message, unicode(msg['message_id']))

    @inlineCallbacks
    def test_get_opt_out(self):
        msg = self.msg_helper.make_inbound("inbound")
        opt_out = yield self.opt_out_store.get_opt_out("msisdn", "+1234")
        self.assertEqual(opt_out, None)
        yield self.opt_out_store.new_opt_out("msisdn", "+1234", msg)
        opt_out = yield self.opt_out_store.get_opt_out("msisdn", "+1234")
        self.assertEqual(opt_out.message, msg['message_id'])

    @inlineCallbacks
    def test_delete_opt_out(self):
        store = self.opt_out_store
        yield store.new_opt_out(
            "msisdn", "+1234", self.msg_helper.make_inbound("inbound"))
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
                addr_type, addr, self.msg_helper.make_inbound("inbound"))
        keys = sorted((yield self.opt_out_store.list_opt_outs()))
        expected_keys = sorted(self.opt_out_store.opt_out_id(addr_type, addr)
                               for addr_type, addr in addrs)
        self.assertEqual(keys, expected_keys)

    @inlineCallbacks
    def test_list_opt_outs_empty(self):
        opt_outs = yield self.opt_out_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

    @inlineCallbacks
    def test_count(self):
        store = self.opt_out_store
        yield store.new_opt_out(
            "msisdn", "+1234", self.msg_helper.make_inbound("inbound"))
        self.assertEqual((yield store.count()), 1)
