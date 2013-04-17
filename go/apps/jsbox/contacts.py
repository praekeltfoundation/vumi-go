# -*- test-case-name: go.apps.jsbox.tests.test_contacts -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.application.sandbox import SandboxResource


class ContactsCommandError(Exception):
    """Raised when erroneous ContactsResource commands are encountered."""


class ContactsResource(SandboxResource):
    def _parse_get(self, command):
        if 'addr' not in command:
            raise ContactsCommandError("'addr' needs to be specified")

        if 'delivery_class' not in command:
            if 'delivery_class' in self.config:
                command['delivery_class'] = self.config['delivery_class']
            else:
                raise ContactsCommandError(
                    "'delivery_class' needs to be specified")

    def _get(self, api, command, create=False):
        try:
            self._parse_get(command)
        except ContactsCommandError, e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        contact_store = self.app_worker.user_api_for_api(api).contact_store
        return contact_store.contact_for_addr(
            command['delivery_class'],
            command['addr'],
            create)

    @inlineCallbacks
    def handle_get(self, api, command):
        contact = yield self._get(api, command, create=False)

        if contact is None:
            returnValue(self.reply(
                command, success=False, reason="Contact not found"))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def handle_get_or_create(self, api, command):
        contact = yield self._get(api, command, create=True)
        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))
