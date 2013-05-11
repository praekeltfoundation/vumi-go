# -*- test-case-name: go.apps.jsbox.tests.test_contacts -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.application.sandbox import SandboxResource, SandboxError

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
            ``twitter``, ``gtalk``
            - ``addr``: The address to use to lookup of the contact. For
            example, if ``sms`` was the delivery class, the address would look
            something like ``+27731112233``

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
            ``false``
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
                    'email_address': null,
                    'name': 'A Random'
                }

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
            log.warning(str(e))
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
        Similar to :method:`handle_get`, but creates the contact if it does
        not yet exist.

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
            ``false``
            - ``contact``: An object containing the contact's data
            - ``created``: ``true`` if a new contact was created, otherwise
            ``false``
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
            log.warning(str(e))
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

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
            ``false``

        Example:
        .. code-block:: javascript
            api.request(
                'contacts.update',
                {key: '123abc',
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
            yield store.update_contact(command['key'], **fields)
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(command, success=True))

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
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(command, success=True))

    def handle_update_extras(self, api, command):
        """
        Updates subfields of an existing contact's ``extra`` field.

        Command field:
            - ``key``: The contact's key
            - ``fields``: The extra fields to be updated

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
            ``false``

        Example:
        .. code-block:: javascript
            api.request(
                'contacts.update_extras',
                {fields: {location: 'CPT', beer: 'Whale Tail Ale'}},
                function(reply) { api.log_info(reply.success); });
        """
        return self._update_dynamic_fields('extra', api, command)

    def handle_update_subscriptions(self, api, command):
        """
        Updates subfields of an existing contact's ``subscription`` field.

        Command field:
            - ``key``: The contact's key
            - ``fields``: The subscription fields to be updated

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
            ``false``

        Example:
        .. code-block:: javascript
            api.request(
                'contacts.update_subscriptions',
                {fields: {a: 'one', b: 'two'}},
                function(reply) { api.log_info(reply.success); });
        """
        return self._update_dynamic_fields('subscription', api, command)

    @inlineCallbacks
    def handle_new(self, api, command):
        """
        Creates a new contacts with the given fields of an existing contact.

        Command fields:
            - ``fields``: The fields to be set for the new contact

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
            ``false``
            - ``key``: a string representing the newly created key identifying
            the contact (for eg. f953710a2472447591bd59e906dc2c26)

        Example:
        .. code-block:: javascript
            api.request(
                'contacts.new',
                {fields: {surname: 'Jones', extra: {location: 'CPT'}}},
                function(reply) { api.log_info(reply.key); });
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
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(command, success=True, key=contact.key))

    @inlineCallbacks
    def handle_save(self, api, command):
        """
        Saves a contact's data, overwriting the contact's previous data. Use
        with care. This operation only works for existing contacts. For
        creating new contacts, use :method:`handle_new`.

        Command fields:
            - ``contact``: The contact's data. **Note**: ``key`` must be a
            field in the contact data in order identify the contact.

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
            ``false``

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
                }, function(reply) { api.log_info(reply.key); });
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

            for group in groups:
                contact.add_to_group(group)

            yield contact.save()
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(command, success=True))
