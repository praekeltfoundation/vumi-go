# -*- coding: utf-8 -*-

"""Tests for go.vumitools.channel.models."""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.channel.models import ChannelStore, CheapPlasticChannel
from go.vumitools.tests.helpers import VumiApiHelper, djangotest


class TestChannel(VumiTestCase):

    def make_channel(self, tagpool_metadata={}):
        return CheapPlasticChannel("pool", "tag", tagpool_metadata, "batch1")

    def test_supports(self):
        channel = self.make_channel({"supports": {"foo": True}})
        self.assertTrue(channel.supports(foo=True))
        self.assertTrue(channel.supports())
        self.assertFalse(channel.supports(foo=False))
        self.assertFalse(channel.supports(bar=True))
        self.assertFalse(channel.supports(foo=True, bar=True))

    def test_supports_generic_sends(self):
        channel = self.make_channel({"supports": {"generic_sends": True}})
        self.assertTrue(channel.supports_generic_sends())
        channel = self.make_channel()
        self.assertFalse(channel.supports_generic_sends())

    def test_supports_replies(self):
        channel = self.make_channel({"supports": {"replies": True}})
        self.assertTrue(channel.supports_replies())
        channel = self.make_channel()
        self.assertFalse(channel.supports_replies())


class TestChannelStore(VumiTestCase):
    is_sync = False

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(
            VumiApiHelper(is_sync=self.is_sync))
        self.user_helper = yield self.vumi_helper.get_or_create_user()
        user_account = yield self.user_helper.get_user_account()
        self.channel_store = ChannelStore.from_user_account(user_account)

    @inlineCallbacks
    def test_get_channel_by_tag(self):
        tag = ["pool", "tag"]
        channel = yield self.channel_store.get_channel_by_tag(
            tag, {}, "batch1")
        self.assertEqual(channel.tagpool, "pool")
        self.assertEqual(channel.tag, "tag")
        self.assertEqual(channel.key, "pool:tag")
        self.assertEqual(channel.name, "tag")
        self.assertEqual(channel.tagpool_metadata, {})
        self.assertEqual(channel.batch.key, "batch1")


@djangotest
class TestChannelStoreSync(TestChannelStore):
    is_sync = True
