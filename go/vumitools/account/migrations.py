from vumi.persist.model import ModelMigrator


class UserAccountMigrator(ModelMigrator):

    def migrate_from_unversioned(self, mdata):
        # Copy stuff that hasn't changed between versions
        mdata.copy_values(
            'username', 'created_at', 'msisdn', 'confirm_start_conversation')
        mdata.copy_indexes('tagpools_bin', 'applications_bin')

        # Add stuff that's new in this version
        mdata.set_value('$VERSION', 1)
        mdata.set_value('tags', None)  # We populate this later
        old_ehconfig = mdata.old_data.get('event_handler_config')
        mdata.set_value('event_handler_config', old_ehconfig or [])

        return mdata
