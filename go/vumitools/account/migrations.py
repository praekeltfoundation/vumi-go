from vumi.persist.model import ModelMigrator


class UserAccountMigrator(ModelMigrator):

    def migrate_from_unversioned(self, mdata):
        # Copy stuff that hasn't changed between versions
        mdata.copy_values('username', 'created_at')
        mdata.copy_indexes('tagpools_bin', 'applications_bin')

        # Copy stuff that may not exist in the source data
        mdata.set_value('msisdn', mdata.old_data.get('msisdn', None))
        mdata.set_value('confirm_start_conversation', mdata.old_data.get(
            'confirm_start_conversation', False))

        # Add stuff that's new in this version
        mdata.set_value('$VERSION', 1)
        mdata.set_value('tags', None)  # We populate this later
        old_ehconfig = mdata.old_data.get('event_handler_config')
        mdata.set_value('event_handler_config', old_ehconfig or [])

        return mdata

    def migrate_from_1(self, mdata):
        # Copy stuff that hasn't changed between versions
        mdata.copy_values(
            'username', 'created_at', 'msisdn', 'confirm_start_conversation',
            'tags', 'event_handler_config')
        mdata.copy_indexes('tagpools_bin', 'applications_bin')

        # Add stuff that's new in this version
        mdata.set_value('$VERSION', 2)
        mdata.set_value('routing_table', None)  # We populate this later

        return mdata
