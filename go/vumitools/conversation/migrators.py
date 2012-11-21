from vumi.persist.model import ModelMigrator


class ConversationV1Migrator(ModelMigrator):
    def migrate_from_unversioned(self, mdata):
        # Copy stuff that hasn't changed between versions
        mdata.copy_values(
            'conversation_type',
            'start_timestamp', 'end_timestamp', 'created_at',
            'delivery_class', 'delivery_tag_pool', 'delivery_tag')
        mdata.copy_indexes('user_account_bin', 'groups_bin', 'batches_bin')

        # Add stuff that's new in this version
        mdata.set_value('VERSION', 1)
        mdata.set_value('name', mdata.old_data['subject'])

        config = (mdata.old_data['metadata'] or {}).copy()
        config['content'] = mdata.old_data['message']
        mdata.set_value('config', config)

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
