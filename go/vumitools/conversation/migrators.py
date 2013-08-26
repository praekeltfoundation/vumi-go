from vumi.persist.model import ModelMigrator, ModelMigrationError


# NOTE: This module must not import anything from Vumi Go at the top level.
#       If individual migrators need such modules, they can import them in
#       their own scope.


class ConversationMigrator(ModelMigrator):

    def migrate_from_unversioned(self, mdata):
        # Copy stuff that hasn't changed between versions
        mdata.copy_values(
            'conversation_type',
            'start_timestamp', 'end_timestamp', 'created_at',
            'delivery_class', 'delivery_tag_pool')
        # Sometimes we don't have a delivery_tag field.
        delivery_tag = mdata.old_data.get('delivery_tag', None)
        mdata.set_value('delivery_tag', delivery_tag)
        mdata.copy_indexes('user_account_bin', 'groups_bin', 'batches_bin')
        # Set values for possible ancient index-only fields.
        mdata.set_value('user_account', mdata.new_index['user_account_bin'][0])
        mdata.set_value('groups', mdata.new_index['groups_bin'])
        mdata.set_value('batches', mdata.new_index['batches_bin'])

        # Add stuff that's new in this version
        mdata.set_value('$VERSION', 1)
        mdata.set_value('name', mdata.old_data['subject'])
        mdata.set_value('description', mdata.old_data['message'])

        mdata.set_value('config', mdata.old_data.get('metadata', None) or {})

        # We don't use the constants here because they may change or disappear
        # underneath us in the future.
        status = u'draft'
        if mdata.new_index['batches_bin']:
            # ^^^ This kind of hackery is part of the reason for the migration.
            status = u'running'
        if mdata.new_data['end_timestamp'] is not None:
            status = u'finished'
        mdata.set_value('status', status, index='status_bin')

        # Add indexes for fields with new (or updated) indexes
        mdata.add_index('end_timestamp_bin', mdata.new_data['end_timestamp'])
        mdata.add_index(
            'start_timestamp_bin', mdata.new_data['start_timestamp'])
        mdata.add_index('created_at_bin', mdata.new_data['created_at'])

        return mdata

    def migrate_from_1(self, mdata):
        # Copy stuff that hasn't changed between versions
        mdata.copy_values(
            'user_account', 'name', 'description', 'conversation_type',
            'config', 'created_at', 'groups', 'batches', 'delivery_class',
            'delivery_tag_pool', 'delivery_tag')
        mdata.copy_indexes(
            'user_account_bin', 'conversation_type_bin', 'created_at_bin',
            'end_timestamp_bin', 'groups_bin', 'batches_bin')

        # Add stuff that's new in this version
        mdata.set_value('$VERSION', 2)
        mdata.set_value('extra_endpoints', [])
        mdata.set_value('archived_at', mdata.old_data['end_timestamp'])

        # We don't use the constants here because they may change or disappear
        # underneath us in the future.
        archive_status = u'active'
        status = u'draft'

        if mdata.old_data['status'] == u'finished':
            archive_status = u'archived'
            status = u'stopped'
        elif mdata.old_data['status'] == u'running':
            status = u'running'
        elif mdata.old_data['status'] == u'draft':
            status = u'stopped'

        mdata.set_value('status', status, index='status_bin')
        mdata.set_value('archive_status', archive_status,
                        index='archive_status_bin')

        return mdata

    def migrate_from_2(self, mdata):
        # Copy stuff that hasn't changed between versions
        mdata.copy_values(
            'user_account', 'name', 'description', 'conversation_type',
            'config', 'created_at', 'groups', 'delivery_class',
            'extra_endpoints', 'archived_at', 'status', 'archive_status')
        mdata.copy_indexes(
            'user_account_bin', 'conversation_type_bin', 'created_at_bin',
            'end_timestamp_bin', 'groups_bin', 'status_bin',
            'archive_status_bin')

        # Add stuff that's new in this version
        mdata.set_value('$VERSION', 3)

        # Handle batches
        if len(mdata.old_data['batches']) != 1:
            # We require exactly one batch, so explode if we have none or lots.
            raise ModelMigrationError((
                "Conversation %s cannot be migrated: Exactly one batch key"
                " required, %s found. Please run a manual 'fix-batches'"
                " conversation migration.") % (mdata.riak_object.get_key(),
                                               len(mdata.old_data['batches'])))

        # By now we have exactly one batch and all is right with the world.
        mdata.set_value('batch', mdata.old_data['batches'][0])

        return mdata
