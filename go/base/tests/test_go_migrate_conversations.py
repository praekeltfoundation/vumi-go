# -*- coding: utf-8 -*-
from uuid import uuid4
from StringIO import StringIO
from datetime import datetime

from vumi.persist.model import ModelMigrationError

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.management.commands import go_migrate_conversations
from go.vumitools.conversation.old_models import ConversationVNone


class GoMigrateConversationsCommandTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(GoMigrateConversationsCommandTestCase, self).setUp()
        self.user = self.mk_django_user()
        self.setup_user_api(self.user)

        self.old_conv_model = self.user_api.conversation_store.manager.proxy(
            ConversationVNone)

        self.conv1 = self.mkoldconv(subject=u'Old 1')
        self.conv2 = self.mkoldconv(subject=u'Old 1')
        self.conv3 = self.mkoldconv(subject=u'Zoë destroyer of Ascii')
        self.convs = [self.conv1, self.conv2, self.conv3]

        self.command = go_migrate_conversations.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def handle_command(self, migration_name=None, list=False, dry_run=False):
        return self.command.handle(migration_name=migration_name, list=list,
                                   dry_run=dry_run)

    def mkoldconv(self, **kwargs):
        conversation_id = uuid4().get_hex()
        groups = kwargs.pop('groups', [])
        conv_fields = {
            'user_account': self.user_api.user_account_key,
            'conversation_type': u'dummy_conv',
            'subject': u'Conversation',
            'message': u'foo',
            'start_timestamp': datetime.utcnow(),
            }
        conv_fields.update(kwargs)
        conversation = self.old_conv_model(conversation_id, **conv_fields)

        for group in groups:
            conversation.add_group(group)

        return conversation.save()

    def test_list_migrators(self):
        self.handle_command(list=True)
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(output[0], 'Available migrations:')
        self.assertEqual(output[2], '  migrate-models:')
        self.assertEqual(output[4:6], [
            '    Load and re-save all conversations, triggering any pending'
            ' model',
            '    migrators in the process.',
        ])
        self.assertEqual(output[7], '  separate-tag-batches:')

    def test_migrate_models_dry_run(self):
        self.handle_command(migration_name='migrate-models', dry_run=True)
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 5)
        self.assertEqual(output[0], 'Test User <username> [test-0-user]')
        self.assertEqual(output[1], '  Migrating 3 of 3 conversations ...')
        for conv in self.convs:
            # If we can load the old model, the data hasn't been migrated.
            loaded_conv = self.old_conv_model.load(conv.key)
            self.assertEqual(conv.subject, loaded_conv.subject)

    def test_migrate_models(self):
        self.handle_command(migration_name='migrate-models')
        output = self.command.stdout.getvalue().strip().split('\n')
        self.assertEqual(len(output), 5)
        self.assertEqual(output[0], 'Test User <username> [test-0-user]')
        self.assertEqual(output[1], '  Migrating 3 of 3 conversations ...')
        extracted_keys = set(line.split()[2]
                             for line in output[2:])
        self.assertEqual(extracted_keys, set(c.key for c in self.convs))
        for conv in self.convs:
            # If the data has been migrated, we can't load the old model.
            try:
                self.old_conv_model.load(conv.key)
                self.fail("Expected ModelMigrationError")
            except ModelMigrationError:
                pass
            # Check that the new model loads correctly.
            loaded_conv = self.user_api.get_wrapped_conversation(conv.key)
            self.assertEqual(conv.subject, loaded_conv.name)
