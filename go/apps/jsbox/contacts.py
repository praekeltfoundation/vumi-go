# -*- test-case-name: go.apps.jsbox.tests.test_contacts -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vxsandbox import SandboxResource, SandboxError

from go.vumitools.contact import (
    Contact, ContactStore, ContactError, ContactNotFoundError)


class ContactsResource(SandboxResource):
    """
    Sandbox resource for accessing, creating and modifying contacts for
    a Go application.

    See :class:`go.vumitools.contact.Contact` for a look at the Contact model
    and its fields.
    """

    def _contact_store_for_api(self, api):
        return self.app_worker.user_api_for_api(api).contact_store

    def _parse_get(self, command):
        if not isinstance(command.get('addr'), unicode):
            raise SandboxError(
                "'addr' needs to be specified and be a unicode string")

        if 'delivery_class' not in command:
            if 'delivery_class' in self.config:
                command['delivery_class'] = self.config['delivery_class']

        if not isinstance(command.get('delivery_class'), unicode):
            raise SandboxError(
                "'delivery_class' needs to be specified and be a unicode "
                "string")

    @inlineCallbacks
    def handle_get(self, api, command):
        """
        Accepts a delivery class and address and returns a contact's data, as
        well as the success flag of the operation (can be ``true`` or
        ``false``).

        Command fields:
            - ``delivery_class``: the type of channel used for the passed in
              address. Can be one of the following types: ``sms``, ``ussd``,
              ``twitter``, ``gtalk``, ``mxit``, ``wechat``.
            - ``addr``: The address to use to lookup of the contact. For
              example, if ``sms`` was the delivery class, the address would
              look something like ``+27731112233``

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data. Looks
              something like this:

            .. code-block:: javascript

                {
                    'key': 'f953710a2472447591bd59e906dc2c26',
                    'surname': 'Person',
                    'user_account': 'test-0-user',
                    'bbm_pin': null,
                    'msisdn': '+27831234567',
                    'created_at': '2013-04-24 14:01:41.803693',
                    'gtalk_id': null,
                    'dob': null,
                    'groups': ['group-a', 'group-b'],
                    'facebook_id': null,
                    '$VERSION': null,
                    'twitter_handle': null,
                    'mxit_id': null,
                    'wechat_id': null,
                    'email_address': null,
                    'name': 'A Random'
                }

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.get',
                {delivery_class: 'sms', addr: '+27731112233'},
                function(reply) { api.log_info(reply.contact.name); });
        """
        try:
            self._parse_get(command)

            contact = yield self._contact_store_for_api(api).contact_for_addr(
                command['delivery_class'],
                command['addr'],
                create=False)
        except (SandboxError, ContactError) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if contact is None:
            returnValue(self.reply(
                command, success=False, reason="Contact not found"))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def handle_get_or_create(self, api, command):
        """
        Similar to :func:`handle_get`, but creates the contact if it does
        not yet exist.

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data
            - ``created``: ``true`` if a new contact was created, otherwise
              ``false``

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure
        """
        try:
            self._parse_get(command)
            contact_store = self._contact_store_for_api(api)
            contact = yield contact_store.contact_for_addr(
                command['delivery_class'],
                command['addr'],
                create=False)
            created = False
        except ContactNotFoundError:
            contact = yield contact_store.new_contact_for_addr(
                command['delivery_class'],
                command['addr'])
            created = True
        except (SandboxError, ContactError) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            created=created,
            contact=contact.get_data()))

    @staticmethod
    def pick_fields(collection, *fields):
        return dict((k, collection[k]) for k in fields if k in collection)

    @inlineCallbacks
    def handle_update(self, api, command):
        """
        Updates the given fields of an existing contact.

        **Note**: All subfields of a Dynamic field such as ``extra`` and
        ``subscription`` are overwritten if specified as one of the fields to
        be updated.

        Command fields:
            - ``key``: The contacts key
            - ``fields``: The contact fields to be updated

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.update', {
                     key: 'f953710a2472447591bd59e906dc2c26',
                     fields: {surname: 'Jones', extra: {location: 'CPT'}}},
                function(reply) { api.log_info(reply.success); });
        """
        try:
            if not isinstance(command.get('key'), unicode):
                raise SandboxError(
                    "'key' needs to be specified and be a unicode string")

            if not isinstance(command.get('fields'), dict):
                raise SandboxError(
                    "'fields' needs to be specified and be a dict of field "
                    "name-values pairs")

            store = self._contact_store_for_api(api)
            fields = self.pick_fields(
                command['fields'], *Contact.field_descriptors)
            contact = yield store.update_contact(command['key'], **fields)
        except (SandboxError, ContactError) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def _update_dynamic_fields(self, dynamic_field_name, api, command):
        try:
            if not isinstance(command.get('key'), unicode):
                raise SandboxError(
                    "'key' needs to be specified and be a unicode "
                    "string")

            if not isinstance(command.get('fields'), dict):
                raise SandboxError(
                    "'fields' needs to be specified and be a dict of field "
                    "name-values pairs")

            fields = command['fields']
            if any(not isinstance(k, unicode) for k in fields.keys()):
                raise SandboxError("All field names need to be unicode")

            if any(not isinstance(v, unicode) for v in fields.values()):
                raise SandboxError("All field values need to be unicode")

            store = self._contact_store_for_api(api)
            contact = yield store.get_contact_by_key(command['key'])

            dynamic_field = getattr(contact, dynamic_field_name)
            for k, v in fields.iteritems():
                dynamic_field[k] = v

            yield contact.save()
        except (SandboxError, ContactError) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    def handle_update_extras(self, api, command):
        """
        Updates subfields of an existing contact's ``extra`` field.

        Command field:
            - ``key``: The contact's key
            - ``fields``: The extra fields to be updated

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.update_extras', {
                    key: f953710a2472447591bd59e906dc2c26',
                    fields: {location: 'CPT', beer: 'Whale Tail Ale'}},
                function(reply) { api.log_info(reply.success); });
        """
        return self._update_dynamic_fields('extra', api, command)

    def handle_update_subscriptions(self, api, command):
        """
        Updates subfields of an existing contact's ``subscription`` field.

        Command field:
            - ``key``: The contact's key
            - ``fields``: The subscription fields to be updated

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.update_subscriptions', {
                    key: f953710a2472447591bd59e906dc2c26',
                    fields: {a: 'one', b: 'two'}},
                function(reply) { api.log_info(reply.success); });
        """
        return self._update_dynamic_fields('subscription', api, command)

    @inlineCallbacks
    def handle_new(self, api, command):
        """
        Creates a new contacts with the given fields of an existing contact.

        Command fields:
            - ``contact``: The contact data to initialise the new contact with.

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.new',
                {contact: {surname: 'Jones', extra: {location: 'CPT'}}},
                function(reply) { api.log_info(reply.success); });
        """
        try:
            if not isinstance(command.get('contact'), dict):
                raise SandboxError(
                    "'contact' needs to be specified and be a dict of field "
                    "name-value pairs")

            fields = self.pick_fields(command['contact'],
                                      *Contact.field_descriptors)
            contact_store = self._contact_store_for_api(api)
            contact = yield contact_store.new_contact(**fields)
        except (SandboxError, ContactError) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def handle_save(self, api, command):
        """
        Saves a contact's data, overwriting the contact's previous data. Use
        with care. This operation only works for existing contacts. For
        creating new contacts, use :func:`handle_new`.

        Command fields:
            - ``contact``: The contact's data. **Note**: ``key`` must be a
              field in the contact data in order identify the contact.

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.save', {
                    contact: {
                        'key': 'f953710a2472447591bd59e906dc2c26',
                        'surname': 'Person',
                        'user_account': 'test-0-user',
                        'msisdn': '+27831234567',
                        'groups': ['group-a', 'group-b'],
                        'name': 'A Random'
                    }
                },
                function(reply) { api.log_info(reply.success); });
        """
        try:
            if not isinstance(command.get('contact'), dict):
                raise SandboxError(
                    "'contact' needs to be specified and be a dict of field "
                    "name-value pairs")

            fields = command['contact']
            if not isinstance(fields.get('key'), unicode):
                raise SandboxError(
                    "'key' needs to be specified as a field in 'contact' and "
                    "be a unicode string")

            # These are foreign keys.
            groups = fields.pop('groups', [])

            key = fields.pop('key')
            contact_store = self._contact_store_for_api(api)

            # raise an exception if the contact does not exist
            yield contact_store.get_contact_by_key(key)

            contact = contact_store.contacts(
                key,
                user_account=contact_store.user_account_key,
                **ContactStore.settable_contact_fields(**fields))

            # since we are basically creating a 'new' contact with the same
            # key, we can be sure that the old groups were removed
            for group in groups:
                contact.add_to_group(group)

            yield contact.save()
        except (SandboxError, ContactError) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def handle_get_by_key(self, api, command):
        """
        Retrieve a contact object by key

        Command fields:
            - ``key``: The key identifying an existing contact.

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: A string describing the reason for the failure

        Examples:

        Retrieve a contact which is known to have key
        '391cea45-ae51-441c-b972-5de765c7a0dc'.

        .. code-block:: javascript

            api.request(
                'contacts.get_by_key', {
                     key: '391cea45-ae51-441c-b972-5de765c7a0dc',
                },
                function(reply) { api.log_info(reply.contact); });

        """
        try:
            if 'key' not in command:
                returnValue(self.reply(
                    command,
                    success=False,
                    reason=u"Expected 'key' field in request"))

            key = command['key']
            contact_store = self._contact_store_for_api(api)
            contact = (yield contact_store.get_contact_by_key(key)).get_data()
        except (ContactNotFoundError, ContactError, SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact))

    @inlineCallbacks
    def handle_search(self, api, command):
        """
        Search for contacts

        Command fields:
            - ``query``: The Lucene search query to perform.
            - ``max_keys``: If present, a non-negative number that specifies
                            the maximum number of keys to return in the result.
                            By default keys for all matching contacts are
                            returned.

        Success reply fields:
            - ``success``: set to ``true``
            - ``keys``: A list of keys for matching contacts.

        Note: If no matches are found ``keys`` will be an empty list.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Examples:

        Searching on a single contact field:

        .. code-block:: javascript

            api.request(
                'contacts.search', {
                     query: 'name:"My Name"',
                },
                function(reply) { api.log_info(reply.keys); });

        """
        try:
            if 'query' not in command:
                returnValue(self.reply(
                    command,
                    success=False,
                    reason=u"Expected 'query' field in request"))
            max_keys = None
            if 'max_keys' in command:
                value = command['max_keys']
                if type(value) is int and value >= 0:
                    max_keys = value
                else:
                    returnValue(self.reply(
                        command,
                        success=False,
                        reason=u"Value for parameter 'max_keys' is invalid"))

            contact_store = self._contact_store_for_api(api)
            keys = yield contact_store.contacts.raw_search(
                command['query']).get_keys()
            if max_keys is not None:
                keys = keys[:max_keys]

        except (SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))
        except (Exception,) as e:
            # NOTE: Hello Riakasaurus, you raise horribly plain exceptions on
            #       a MapReduce error.
            if 'MapReduce' not in str(e):
                raise
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            keys=keys))


class GroupsResource(SandboxResource):
    """
    Sandbox resource for accessing, creating and modifying groups for
    a Go application.

    See :class:`go.vumitools.contact.ContactGroup` for a look at the Contact
    model and its fields.
    """

    def _contact_store_for_api(self, api):
        return self.app_worker.user_api_for_api(api).contact_store

    @inlineCallbacks
    def handle_search(self, api, command):
        """
        Search for groups

        Command fields:
            - ``query``: The Lucene search query to perform.

        Success reply fields:
            - ``success``: set to ``true``
            - ``groups``: An list of dictionaries with group information.

        Note:   If no matches are found ``groups`` will be an empty list.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.search', {
                     query: 'name:"My Group"',
                },
                function(reply) { api.log_info(reply.groups); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            keys = yield contact_store.groups.raw_search(
                command['query']).get_keys()
            groups = []
            for group_bunch in contact_store.groups.load_all_bunches(keys):
                groups.extend((yield group_bunch))

        except (SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))
        except (Exception,) as e:
            # NOTE: Hello Riakasaurus, you raise horribly plain exceptions on
            #       a MapReduce error.
            if 'MapReduce' not in str(e):
                raise
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            groups=[group.get_data() for group in groups]))

    @inlineCallbacks
    def handle_get(self, api, command):
        """
        Get a group by its key

        Command fields:
            - ``key``: The key of the group to retrieve

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.get', {
                     key: 'a-key',
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            group = yield contact_store.get_group(command['key'])
        except (SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if group is None:
            returnValue(self.reply(
                command, success=False, reason='Group not found'))

        returnValue(self.reply(
            command,
            success=True,
            group=group.get_data()))

    @inlineCallbacks
    def handle_get_by_name(self, api, command):
        """
        Get a group by its name

        Command fields:
            - ``name``: The key of the group to retrieve

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Note:   If more than 1 matching groups are found a Failure reply is
                returned.

        Example:

        .. code-block:: javascript

            api.request(
                'groups.get_by_name', {
                     name: 'My Group',
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            keys = yield contact_store.groups.search(
                name=command['name']).get_keys()
        except (SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))
        except (Exception,) as e:
            # NOTE: Hello Riakasaurus, you raise horribly plain exceptions on
            #       a MapReduce error.
            if 'MapReduce' not in str(e):
                raise
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if not keys:
            returnValue(self.reply(
                command, success=False, reason='Group not found'))

        if len(keys) != 1:
            returnValue(self.reply(
                command, success=False, reason='Multiple groups found'))

        [key] = keys
        group = yield contact_store.get_group(key)
        returnValue(self.reply(
            command, success=True, group=group.get_data()))

    @inlineCallbacks
    def handle_get_or_create_by_name(self, api, command):
        """
        Get or create a group by its name

        Command fields:
            - ``name``: The name of the group to get or create

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's data.
            - ``created``: A boolean, ``True`` if created, ``False`` if not.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.get_or_create_by_name', {
                     name: 'My Group',
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            keys = yield contact_store.groups.search(
                name=command['name']).get_keys()
        except (SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))
        except (Exception,) as e:
            # NOTE: Hello Riakasaurus, you raise horribly plain exceptions on
            #       a MapReduce error.
            if 'MapReduce' not in str(e):
                raise
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if not keys:
            group = yield contact_store.new_group(command['name'])
            returnValue(self.reply(
                command, success=True, created=True, group=group.get_data()))

        if len(keys) != 1:
            returnValue(self.reply(
                command, success=False, reason='Multiple groups found'))

        [key] = keys
        group = yield contact_store.get_group(key)
        returnValue(self.reply(
            command, success=True, created=False, group=group.get_data()))

    @inlineCallbacks
    def handle_update(self, api, command):
        """
        Update a group's name or query.

        Command fields:
            - ``key``: The key of the group to retrieve
            - ``name``: The new name
            - ``query``: The query to store, defaults to ``None``.

        Note:   If a ``query`` is provided the group is treated as a
                "smart" group.

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's updated data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.update', {
                     key: 'a-key',
                     name: 'My New Group',
                     query: 'name:foo*'
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            group = yield contact_store.get_group(command['key'])
        except (SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if group is None:
            returnValue(self.reply(
                command, success=False, reason='Group not found'))

        group.name = command['name']
        group.query = command.get('query', None)
        yield group.save()

        returnValue(self.reply(
            command,
            success=True,
            group=group.get_data()))

    @inlineCallbacks
    def handle_count_members(self, api, command):
        """
        Count the number of members in a group.

        Command fields:
            - ``key``: The key of the group to retrieve

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's data.
            - ``count``: The number of members in this group.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.count_members', {
                     key: 'a-key'
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            group = yield contact_store.get_group(command['key'])
        except (SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        member_count = yield contact_store.count_contacts_for_group(group)
        returnValue(self.reply(
            command, success=True, count=member_count, group=group.get_data()))

    @inlineCallbacks
    def handle_list(self, api, command):
        """
        List all known groups

        Command fields: None

        Success reply fields:
            - ``success``: set to ``true``
            - ``groups``: A list of dictionaries with group data

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.list', {},
                function(reply) { api.log_info(reply.groups); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            groups = yield contact_store.list_groups()
        except (SandboxError,) as e:
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command, success=True,
            groups=[group.get_data() for group in groups]))
