# -*- test-case-name: go.apps.jsbox.tests.test_contacts -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.application.sandbox import SandboxResource, SandboxError

from go.vumitools.contact import Contact


class ContactsResource(SandboxResource):
    def _contact_store_for_api(self, api):
        return self.app_worker.user_api_for_api(api).contact_store

    def _parse_get(self, command):
        if 'addr' not in command:
            raise SandboxError("'addr' needs to be specified for command")

        if 'delivery_class' not in command:
            if 'delivery_class' in self.config:
                command['delivery_class'] = self.config['delivery_class']
            else:
                raise SandboxError(
                    "'delivery_class' needs to be specified for command")

    @inlineCallbacks
    def handle_get(self, api, command):
        try:
            self._parse_get(command)

            contact = yield self._contact_store_for_api(api).contact_for_addr(
                command['delivery_class'],
                command['addr'],
                create=False)
        except (SandboxError, RuntimeError) as e:
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
        try:
            self._parse_get(command)
            contact = yield self._contact_store_for_api(api).contact_for_addr(
                command['delivery_class'],
                command['addr'],
                create=True)
        except (SandboxError, RuntimeError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    def _filter_contact_fields(self, command):
        """
        Returns only the fields of a command that are Contact model fields.
        """
        return dict((k, command[k]) for k in Contact.field_descriptors.keys()
                    if k in command)

    @inlineCallbacks
    def handle_update(self, api, command):
        try:
            if 'key' not in command:
                raise SandboxError("'key' needs to be specified for command")

            contact = yield self._contact_store_for_api(api).update_contact(
                command['key'], **self._filter_contact_fields(command))
        except (SandboxError, RuntimeError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def handle_new(self, api, command):
        contact = yield self._contact_store_for_api(api).new_contact(
            **self._filter_contact_fields(command))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))
