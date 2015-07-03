# -*- coding: utf-8 -*-
import json
from uuid import uuid4
from StringIO import StringIO
from datetime import datetime

from vumi.persist.model import ModelMigrationError

from go.base.management.commands import go_migrate_conversations
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.vumitools.conversation.old_models import ConversationV1
from go.vumitools.tests.helpers import GoMessageHelper


def collect_all_results(index_page, results=None):
    if results is None:
        results = set()
    while index_page is not None:
        results.update(index_page)
        index_page = index_page.next_page()
    return results


class TestGoMigrateConversationsCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_api = self.vumi_helper.make_django_user().user_api

        conv_store = self.user_api.conversation_store
        self.old_conv_model = conv_store.manager.proxy(ConversationV1)

        self.command = go_migrate_conversations.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def handle_command(self, migration_name=None, list_migrations=False,
                       dry_run=False):
        self.command.handle(migration_name=migration_name,
                            list_migrations=list_migrations,
                            dry_run=dry_run)
        output = self.command.stdout.getvalue().strip().split('\n')
        return output

    def assert_stderr_equals(self, expected_value):
        self.assertEqual(self.command.stderr.getvalue(), expected_value)

    def assert_no_stderr(self):
        self.assert_stderr_equals('')

    def assert_conversations_migrated(self, conversations, output):
        extracted_keys = set(line.split()[2] for line in output
                             if 'Migrating conversation:' in line)
        self.assertEqual(extracted_keys, set(c.key for c in conversations))

    def mkoldconv(self, create_batch=True, **kwargs):
        conversation_id = uuid4().get_hex()
        groups = kwargs.pop('groups', [])
        conv_fields = {
            'user_account': self.user_api.user_account_key,
            'conversation_type': u'dummy_conv',
            'name': u'foo',
            'description': u'Conversation',
            'start_timestamp': datetime.utcnow(),
            'status': u'draft',
            }
        conv_fields.update(kwargs)
        conversation = self.old_conv_model(conversation_id, **conv_fields)

        if create_batch:
            batch_manager = self.user_api.api.get_batch_manager()
            conversation.batches.add_key(batch_manager.batch_start())

        for group in groups:
            conversation.add_group(group)

        return conversation.save()

    def test_list_migrators(self):
        output = self.handle_command(list_migrations=True)
        self.assert_no_stderr()
        self.assertEqual(output[0], 'Available migrations:')
        self.assertEqual(output[2], '  migrate-models:')
        self.assertEqual(output[4:6], [
            '    Load and re-save all conversations, triggering any pending'
            ' model',
            '    migrators in the process.',
        ])
        self.assertEqual(output[7], '  fix-batches:')

    def test_unknown_migration(self):
        output = self.handle_command(migration_name='unknown-migration')
        self.assert_stderr_equals('Unknown migration unknown-migration.\n')
        self.assertEqual(output, [''])

    def setup_migrate_models(self):
        conv1 = self.mkoldconv(name=u'Old 1')
        conv2 = self.mkoldconv(name=u'Old 1')
        conv3 = self.mkoldconv(name=u'Zoë destroyer of Ascii')
        return [conv1, conv2, conv3]

    def test_migrate_models_dry_run(self):
        convs = self.setup_migrate_models()
        output = self.handle_command(
            migration_name='migrate-models', dry_run=True)
        self.assert_no_stderr()
        self.assertEqual(len(output), 5)
        self.assertEqual(
            output[0], 'Test User <user@domain.com> [test-0-user]')
        self.assertEqual(output[1], '  Migrating 3 of 3 conversations ...')
        for conv in convs:
            # If we can load the old model, the data hasn't been migrated.
            loaded_conv = self.old_conv_model.load(conv.key)
            self.assertEqual(conv.name, loaded_conv.name)

    def test_migrate_models(self):
        convs = self.setup_migrate_models()
        output = self.handle_command(migration_name='migrate-models')
        self.assert_no_stderr()
        self.assertEqual(len(output), 5)
        self.assertEqual(
            output[0], 'Test User <user@domain.com> [test-0-user]')
        self.assertEqual(output[1], '  Migrating 3 of 3 conversations ...')
        self.assert_conversations_migrated(convs, output)
        for conv in convs:
            # If the data has been migrated, we can't load the old model.
            try:
                self.old_conv_model.load(conv.key)
                self.fail("Expected ModelMigrationError")
            except ModelMigrationError:
                pass
            # Check that the new model loads correctly.
            loaded_conv = self.user_api.get_wrapped_conversation(conv.key)
            self.assertEqual(conv.name, loaded_conv.name)

    def setup_fix_batches(self, tags=(), num_batches=1):
        FIXME_mdb = self.user_api.api.FIXME_mdb
        msg_helper = GoMessageHelper()  # We can't use .store_*(), so no mdb.
        batches = [FIXME_mdb.batch_start(tags=tags) for i in range(num_batches)]

        conv = self.mkoldconv(
            create_batch=False, conversation_type=u'dummy_type',
            name=u'Dummy Conv 1', description=u'Dummy Description',
            config={})

        for i, batch_id in enumerate(batches):
            conv.batches.add_key(batch_id)
            msg1 = msg_helper.make_inbound("in", message_id=u"msg-%d" % i)
            FIXME_mdb.add_inbound_message(msg1, batch_ids=[batch_id])
            msg2 = msg_helper.make_outbound("out", message_id=u"msg-%d" % i)
            FIXME_mdb.add_outbound_message(msg2, batch_ids=[batch_id])

        conv.save()

        return conv

    def assert_batches_fixed(self, old_conv):
        old_batches = old_conv.batches.keys()
        new_conv = self.user_api.conversation_store.get_conversation_by_key(
            old_conv.key)
        new_batch = new_conv.batch.key
        self.assertTrue(new_batch not in old_batches)

        FIXME_mdb = self.user_api.api.FIXME_mdb
        old_outbound, old_inbound = set(), set()
        for batch in old_batches:
            collect_all_results(
                FIXME_mdb.batch_outbound_keys_page(batch), old_outbound)
            collect_all_results(
                FIXME_mdb.batch_inbound_keys_page(batch), old_inbound)

        new_outbound = collect_all_results(
            FIXME_mdb.batch_outbound_keys_page(new_batch))
        new_inbound = collect_all_results(
            FIXME_mdb.batch_inbound_keys_page(new_batch))
        self.assertEqual(new_outbound, old_outbound)
        self.assertEqual(new_inbound, old_inbound)

    def _check_fix_batches(self, migration_name, tags, num_batches, migrated):
        conv = self.setup_fix_batches(tags, num_batches)
        output = self.handle_command(migration_name=migration_name)
        self.assert_no_stderr()
        self.assertEqual(output[:2], [
            'Test User <user@domain.com> [test-0-user]',
            '  Migrating %d of 1 conversations ...'
            % (1 if migrated else 0)
        ])
        self.assert_conversations_migrated([conv] if migrated else [], output)
        if migrated:
            self.assert_batches_fixed(conv)

    def check_fix_batches(self, tags, num_batches, migrated):
        return self._check_fix_batches(
            'fix-batches', tags, num_batches, migrated)

    def check_split_batches(self, tags, num_batches, migrated):
        return self._check_fix_batches(
            'split-batches', tags, num_batches, migrated)

    def test_fix_batches_on_conv_with_single_batch_with_no_tag(self):
        self.check_fix_batches(tags=(), num_batches=1, migrated=False)

    def test_fix_batches_ignores_newer_conv(self):
        self.user_api.new_conversation(u'dummy_conv', u'Dummy conv', u'', {})
        output = self.handle_command(migration_name='fix-batches')
        self.assert_no_stderr()
        self.assertEqual(output[:2], [
            'Test User <user@domain.com> [test-0-user]',
            '  Migrating 0 of 1 conversations ...',
        ])
        self.assert_conversations_migrated([], output)

    def test_fix_batches_on_conv_with_multiple_batches(self):
        self.check_fix_batches(tags=(), num_batches=2, migrated=True)

    def test_fix_batches_on_conv_with_zero_batches(self):
        self.check_fix_batches(tags=(), num_batches=0, migrated=True)

    def test_split_batches_on_conv_with_single_batch_with_no_tag(self):
        self.check_split_batches(tags=(), num_batches=1, migrated=False)

    def test_split_batches_on_conv_with_batch_with_tag(self):
        self.check_split_batches(tags=[(u"pool", u"tag")],
                               num_batches=1, migrated=True)

    def test_fix_jsbox_endpoints(self):
        app_config = {
            "config": {
                "value": json.dumps({
                    "sms_tag": ["foo", "bar"],
                }),
                "source_url": u"",
            }
        }
        old_conv = self.user_api.conversation_store.new_conversation(
            u'jsbox', u'Dummy Jsbox', u'Dummy Description',
            {"jsbox_app_config": app_config}, u"dummy-batch")
        self.assertEqual(sorted(old_conv.extra_endpoints), [])
        output = self.handle_command(migration_name='fix-jsbox-endpoints')
        self.assertEqual(output, [
            'Test User <user@domain.com> [test-0-user]',
            '  Migrating 1 of 1 conversations ...',
            '    Migrating conversation: %s [Dummy Jsbox] ... done.'
            % (old_conv.key),
        ])
        new_conv = self.user_api.conversation_store.get_conversation_by_key(
            old_conv.key)
        self.assertEqual(sorted(new_conv.extra_endpoints),
                         ["foo:bar"])

    def test_fix_jsbox_endpoints_skips_non_jsbox(self):
        self.user_api.conversation_store.new_conversation(
            u'dummy_type', u'Dummy Conv 1', u'Dummy Description',
            {}, u"dummy-batch")
        output = self.handle_command(migration_name='fix-jsbox-endpoints')
        self.assertEqual(output, [
            'Test User <user@domain.com> [test-0-user]',
            '  Migrating 0 of 1 conversations ...',
        ])
