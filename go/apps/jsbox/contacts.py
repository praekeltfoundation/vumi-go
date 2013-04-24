# -*- test-case-name: go.apps.jsbox.tests.test_contacts -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.persist.fields import ValidationError
from vumi.application.sandbox import SandboxResource, SandboxError

from go.vumitools.contact import Contact, ContactError


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
        well as the success status of the operation (can be `true` or `false`).

        Command fields:
            :param delivery_class: The type of channel used for the passed in
            address. Can be one of the following types: `sms`, `ussd`,
            `twitter`, `gtalk`
            :param addr: The address to use to lookup of the contact.For
            example, if `sms` was the delivery class, the address would look
            something like `+27731112233`

        Example:
        .. code-block:: javascript
            api.request(
                'contacts.get',
                {deliver_class: 'sms', addr: '+27731112233'},
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
        Behaves the same as :method:handle_get, but creates the contact if it
        does not yet exist.
        """
        try:
            self._parse_get(command)
            contact = yield self._contact_store_for_api(api).contact_for_addr(
                command['delivery_class'],
                command['addr'],
                create=True)
        except (ValidationError, SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @staticmethod
    def pick_fields(collection, *fields):
        return dict((k, collection[k]) for k in fields if k in collection)

    @inlineCallbacks
    def handle_update(self, api, command):
        """
        Updates the given fields of an existing contact and returns the success
        status of the operation (can be `true` or `false`).

        **Note**: All subfields of a Dynamic field such as `extra` and
        `subscription` are overwritten if specified as one of the fields to be
        updated (see example below).

        Command field:
            :param key: The contacts key
            :param fields: The contact fields to be updated

        Example:
        .. code-block:: javascript
            api.request(
                'contacts.update',
                {key: '123abc', surname: 'Jones', extra: {location: 'CPT'}},
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
    def _update_dynamic_field(self, field_name, api, command):
        try:
            if not isinstance(command.get('contact_key'), unicode):
                raise SandboxError(
                    "'contact_key' needs to be specified and be a unicode "
                    "string")

            if not isinstance(command.get('field'), unicode):
                raise SandboxError(
                    "'field' needs to be specified and be a unicode string")

            if command.get('value') is None:
                raise SandboxError("'value' needs to be specified and be a "
                                   "non-None value")

            store = self._contact_store_for_api(api)
            contact = yield store.get_contact_by_key(command['contact_key'])

            field = getattr(contact, field_name)
            field[command['field']] = command['value']
            yield contact.save()
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(command, success=True))

    def handle_update_extra(self, api, command):
        """
        Updates a single subfield of an existing contact's `extra` field and
        returns the success status of the operation (can be `true` or `false`).

        Command field:
            :param contact_key: The contact's key
            :param field: The name of the subfield to be updated
            :param value: The subfield's new value

        Example:
        .. code-block:: javascript
            api.request(
                'contacts.update_extra',
                {contact_key: '123abc', field: 'surname', value: 'Jones'},
                function(reply) { api.log_info(reply.success); });
        """
        return self._update_dynamic_field('extra', api, command)

    def handle_update_subscription(self, api, command):
        """
        Updates a single subfield of an existing contact's `subscription` field
        and returns the success status of the operation (can be `true` or
        `false`).

        Command field:
            :param contact_key: The contact's key
            :param field: The name of the subfield to be updated
            :param value: The subfield's new value

        Example:
        .. code-block:: javascript
            api.request(
                'contacts.update_subscription',
                {contact_key: '123abc', field: 'foo', value: 'bar'},
                function(reply) { api.log_info(reply.success); });
        """
        return self._update_dynamic_field('subscription', api, command)

    @inlineCallbacks
    def handle_new(self, api, command):
        """
        Creates a new contacts with the given fields of an existing contact and
        returns a the new contact's key and the success status of the
        operation (can be `true` or `false`).

        Command field:
            :param fields: The fields to be set for the new contact

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

            # ensure user account can't be changed
            fields.pop('user_account', None)

            # These are foreign keys.
            groups = fields.pop('groups', [])

            # raise an exception if the contact does not exist
            key = fields.pop('key')
            contact_store = self._contact_store_for_api(api)
            yield contact_store.get_contact_by_key(key)

            contact = contact_store.contacts(
                key,
                user_account=contact_store.user_account_key,
                **fields)

            for group in groups:
                contact.add_to_group(group)

            yield contact.save()
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(command, success=True))
