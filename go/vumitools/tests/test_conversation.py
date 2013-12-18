# -*- coding: utf-8 -*-

"""Tests for go.vumitools.conversation."""

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import inlineCallbacks

from vumi.persist.model import ModelMigrationError
from vumi.tests.helpers import VumiTestCase

from go.vumitools.tests.utils import model_eq
from go.vumitools.conversation import ConversationStore
from go.vumitools.opt_out import OptOutStore
from go.vumitools.contact import ContactStore
from go.vumitools.conversation.old_models import (
    ConversationVNone, ConversationV1, ConversationV2)
from go.vumitools.tests.helpers import VumiApiHelper


class TestConversationStore(VumiTestCase):
    is_sync = False

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(
            VumiApiHelper(is_sync=self.is_sync))
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        user_account = yield self.user_helper.get_user_account()
        self.optout_store = OptOutStore.from_user_account(user_account)
        self.conv_store = ConversationStore.from_user_account(user_account)
        self.contact_store = ContactStore.from_user_account(user_account)

    def assert_models_equal(self, m1, m2):
        self.assertTrue(model_eq(m1, m2),
                        "Models not equal:\na: %r\nb: %r" % (m1, m2))

    def assert_models_not_equal(self, m1, m2):
        self.assertFalse(model_eq(m1, m2),
                         "Models unexpectedly equal:\na: %r\nb: %r" % (m1, m2))

    @inlineCallbacks
    def test_new_conversation(self):
        conversations = yield self.conv_store.list_conversations()
        self.assertEqual([], conversations)

        conv = yield self.conv_store.new_conversation(
            u'bulk_message', u'name', u'desc', {u'foo': u'bar'}, u'batch1')
        self.assertEqual(u'bulk_message', conv.conversation_type)
        self.assertEqual(u'name', conv.name)
        self.assertEqual(u'desc', conv.description)
        self.assertEqual({u'foo': u'bar'}, conv.config)
        self.assertEqual(u'batch1', conv.batch.key)
        self.assertEqual(u'active', conv.archive_status)
        self.assertEqual(u'stopped', conv.status)

        dbconv = yield self.conv_store.get_conversation_by_key(conv.key)
        self.assert_models_equal(conv, dbconv)

    @inlineCallbacks
    def test_new_conversation_unicode(self):
        conversations = yield self.conv_store.list_conversations()
        self.assertEqual([], conversations)

        conv = yield self.conv_store.new_conversation(
            u'bulk_message', u'Zoë destroyer of Ascii', u'Return of Zoë!',
            {u'foo': u'Zoë again.'}, u'batch1')
        self.assertEqual(u'bulk_message', conv.conversation_type)
        self.assertEqual(u'Zoë destroyer of Ascii', conv.name)
        self.assertEqual(u'Return of Zoë!', conv.description)
        self.assertEqual({u'foo': u'Zoë again.'}, conv.config)
        self.assertEqual(u'batch1', conv.batch.key)
        self.assertEqual(u'active', conv.archive_status)
        self.assertEqual(u'stopped', conv.status)

        dbconv = yield self.conv_store.get_conversation_by_key(conv.key)
        self.assert_models_equal(conv, dbconv)

    @inlineCallbacks
    def test_get_conversation_vnone(self):
        conversation_id = uuid4().get_hex()

        conv = ConversationVNone(
            self.conv_store.manager,
            conversation_id, user_account=self.conv_store.user_account_key,
            conversation_type=u'bulk_message',
            subject=u'subject', message=u'message',
            start_timestamp=datetime.utcnow())
        conv.batches.add_key('batch_key_1')
        yield conv.save()

        dbconv = yield self.conv_store.get_conversation_by_key(conv.key)

        self.assertEqual(u'bulk_message', dbconv.conversation_type)
        self.assertEqual(u'subject', dbconv.name)
        self.assertEqual(u'message', dbconv.description)
        self.assertEqual({}, dbconv.config)
        self.assertEqual('batch_key_1', dbconv.batch.key)
        self.assertEqual(u'active', dbconv.archive_status)
        self.assertEqual(u'running', dbconv.status)

    @inlineCallbacks
    def test_get_conversation_v1(self):
        conversation_id = uuid4().get_hex()

        conv = ConversationV1(
            self.conv_store.manager,
            conversation_id, user_account=self.conv_store.user_account_key,
            conversation_type=u'bulk_message', name=u'name',
            description=u'description', status=u'draft',
            start_timestamp=datetime.utcnow())
        conv.batches.add_key('batch_key_1')
        yield conv.save()

        dbconv = yield self.conv_store.get_conversation_by_key(conv.key)

        self.assertEqual(u'bulk_message', dbconv.conversation_type)
        self.assertEqual(u'name', dbconv.name)
        self.assertEqual(u'description', dbconv.description)
        self.assertEqual({}, dbconv.config)
        self.assertEqual('batch_key_1', dbconv.batch.key)
        self.assertEqual(u'active', dbconv.archive_status)
        self.assertEqual(u'stopped', dbconv.status)

    @inlineCallbacks
    def test_get_conversation_v2(self):
        conversation_id = uuid4().get_hex()

        conv = ConversationV2(
            self.conv_store.manager,
            conversation_id, user_account=self.conv_store.user_account_key,
            conversation_type=u'bulk_message', name=u'name',
            description=u'description', delivery_tag_pool=u'pool',
            delivery_tag=u'tag')
        conv.batches.add_key('batch_key_1')
        yield conv.save()

        dbconv = yield self.conv_store.get_conversation_by_key(conv.key)

        self.assertEqual(u'bulk_message', dbconv.conversation_type)
        self.assertEqual(u'name', dbconv.name)
        self.assertEqual(u'description', dbconv.description)
        self.assertEqual({}, dbconv.config)
        self.assertEqual('batch_key_1', dbconv.batch.key)
        self.assertEqual(u'active', dbconv.archive_status)
        self.assertEqual(u'stopped', dbconv.status)

    def assert_batch_key_migration_error(self, e, count, conv_key):
        self.assertEqual(e.message, (
            "Conversation %s cannot be migrated: Exactly one batch key"
            " required, %s found. Please run a manual 'fix-batches'"
            " conversation migration.") % (conv_key, count))

    @inlineCallbacks
    def test_get_conversation_v2_no_batch_keys(self):
        conversation_id = uuid4().get_hex()

        conv = ConversationV2(
            self.conv_store.manager,
            conversation_id, user_account=self.conv_store.user_account_key,
            conversation_type=u'bulk_message', name=u'name',
            description=u'description', delivery_tag_pool=u'pool',
            delivery_tag=u'tag')
        yield conv.save()

        try:
            yield self.conv_store.get_conversation_by_key(conv.key)
            self.fail('Expected ModelMigrationError to be raised.')
        except ModelMigrationError as e:
            self.assert_batch_key_migration_error(e, 0, conv.key)

    @inlineCallbacks
    def test_get_conversation_v2_multiple_batch_keys(self):
        conversation_id = uuid4().get_hex()

        conv = ConversationV2(
            self.conv_store.manager,
            conversation_id, user_account=self.conv_store.user_account_key,
            conversation_type=u'bulk_message', name=u'name',
            description=u'description', delivery_tag_pool=u'pool',
            delivery_tag=u'tag')
        conv.batches.add_key('batch_key_1')
        conv.batches.add_key('batch_key_2')
        yield conv.save()

        try:
            yield self.conv_store.get_conversation_by_key(conv.key)
            self.fail('Expected ModelMigrationError to be raised.')
        except ModelMigrationError as e:
            self.assert_batch_key_migration_error(e, 2, conv.key)


class TestConversationStoreSync(TestConversationStore):
    sync_persistence = True
