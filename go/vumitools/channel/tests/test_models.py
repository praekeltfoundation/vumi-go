# -*- coding: utf-8 -*-

"""Tests for go.vumitools.channel.models."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.account import AccountStore
from go.vumitools.channel.models import ChannelStore, CheapPlasticChannel


class TestChannel(TestCase):

    def test_supports(self):
        channel = CheapPlasticChannel("pool", "tag", {
            "supports": {"foo": True}})
        self.assertTrue(channel.supports(foo=True))
        self.assertTrue(channel.supports())
        self.assertFalse(channel.supports(foo=False))
        self.assertFalse(channel.supports(bar=True))
        self.assertFalse(channel.supports(foo=True, bar=True))

    def test_supports_generic_sends(self):
        channel = CheapPlasticChannel("pool", "tag", {
            "supports": {"generic_sends": True}})
        self.assertTrue(channel.supports_generic_sends())
        channel = CheapPlasticChannel("pool", "tag", {})
        self.assertFalse(channel.supports_generic_sends())

    def test_supports_replies(self):
        channel = CheapPlasticChannel("pool", "tag", {
            "supports": {"replies": True}})
        self.assertTrue(channel.supports_replies())
        channel = CheapPlasticChannel("pool", "tag", {})
        self.assertFalse(channel.supports_replies())


class TestChannelStore(GoPersistenceMixin, TestCase):
    use_riak = True
    timeout = 5

    @inlineCallbacks
    def setUp(self):
        yield self._persist_setUp()
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        self.account = yield self.mk_user(self, u'user')
        self.channel_store = ChannelStore.from_user_account(self.account)

    def tearDown(self):
        return self._persist_tearDown()

    @inlineCallbacks
    def test_get_channel_by_tag(self):
        tag = ["pool", "tag"]
        channel = yield self.channel_store.get_channel_by_tag(tag, {})
        self.assertEqual(channel.tagpool, "pool")
        self.assertEqual(channel.tag, "tag")
        self.assertEqual(channel.key, "pool:tag")
        self.assertEqual(channel.name, "tag")
        self.assertEqual(channel.tagpool_metadata, {})


class TestChannelStoreSync(TestChannelStore):
    sync_persistence = True
