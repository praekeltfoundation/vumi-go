# -*- coding: utf-8 -*-

"""Tests for go.vumitools.channel.models."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.account import AccountStore
from go.vumitools.channel.models import ChannelStore


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

    @inlineCallbacks
    def test_get_channel_by_tag(self):
        tag = ["pool", "tag"]
        channel = yield self.channel_store.get_channel_by_tag(tag)
        self.assertEqual(channel.tagpool, "pool")
        self.assertEqual(channel.tag, "tag")
        self.assertEqual(channel.key, "pool:tag")
        self.assertEqual(channel.name, "tag")
        self.assertEqual(channel.tagpool_metadata, None)


class TestChannelStoreSync(TestChannelStore):
    sync_persistence = True
