# -*- test-case-name: go.apps.jsbox.tests.test_contacts -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.application.sandbox import SandboxResource

from go.vumitools.contact import Contact


class ContactsCommandError(Exception):
    """Raised when erroneous ContactsResource commands are encountered."""


class ContactsResource(SandboxResource):
    def _contact_store_for_api(self, api):
        return self.app_worker.user_api_for_api(api).contact_store

    def _parse_get(self, command):
        if 'addr' not in command:
            raise ContactsCommandError("'addr' needs to be specified")

        if 'delivery_class' not in command:
            if 'delivery_class' in self.config:
                command['delivery_class'] = self.config['delivery_class']
            else:
                raise ContactsCommandError(
                    "'delivery_class' needs to be specified")

    @inlineCallbacks
    def handle_get(self, api, command):
        try:
            self._parse_get(command)
        except ContactsCommandError, e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        contact = yield self._contact_store_for_api(api).contact_for_addr(
            command['delivery_class'],
            command['addr'],
            create=False)

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
        except ContactsCommandError, e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        contact = yield self._contact_store_for_api(api).contact_for_addr(
            command['delivery_class'],
            command['addr'],
            create=True)

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def handle_update(self, api, command):
        try:
            if 'key' not in command:
                raise ContactsCommandError("'key' needs to be specified")
        except ContactsCommandError, e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        # get the contact the fields to be updated
        fields = dict(
            (k, command[k]) for k in Contact.field_descriptors.keys()
            if k in command)

        contact_store = self._contact_store_for_api(api)
        contact = yield contact_store.update_contact(command['key'], **fields)
        if contact is None:
            returnValue(self.reply(
                command, success=False, reason="Contact not found"))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))
