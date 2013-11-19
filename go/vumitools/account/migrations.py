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

    def migrate_from_2(self, mdata):
        # There are no schema changes here, but we've tightened up some
        # validation and added a new field type to work with routing tables.

        # Copy stuff that hasn't changed between versions
        mdata.copy_values(
            'username', 'created_at', 'msisdn', 'confirm_start_conversation',
            'tags', 'event_handler_config', 'routing_table')
        mdata.copy_indexes('tagpools_bin', 'applications_bin')

        # We no longer allow nulls in these fields, so set them to empty.
        if mdata.new_data['tags'] is None:
            mdata.set_value('tags', [])
        if mdata.new_data['routing_table'] is None:
            mdata.set_value('routing_table', {})

        # Add stuff that's new in this version
        mdata.set_value('$VERSION', 3)

        return mdata

    def migrate_from_3(self, mdata):
        """
        Add the can_manage_optouts boolean and default it to ``False``
        """

        # Copy stuff that hasn't changed between versions
        mdata.copy_values(
            'username', 'created_at', 'msisdn', 'confirm_start_conversation',
            'tags', 'event_handler_config', 'routing_table')
        mdata.copy_indexes('tagpools_bin', 'applications_bin')

        # set the default `can_manage_optouts` value
        mdata.set_value('can_manage_optouts', False)

        # increment version counter
        mdata.set_value('$VERSION', 4)

        return mdata
