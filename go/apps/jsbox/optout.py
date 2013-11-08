# -*- test-case-name: go.apps.jsbox.tests.test_optout -*-
# -*- coding: utf-8 -*-

"""Resource for accessing and modifying a contact's opt-out/opt-in
   status from the sandbox"""

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.sandbox import SandboxResource
from vumi import log


class OptoutResource(SandboxResource):

    def optout_store_for_api(self, api):
        return self.app_worker.user_api_for_api(api).optout_store

    @inlineCallbacks
    def handle_status(self, api, command):
        """
        Accepts an msisdn and retrieves the opt-out entry for
        it.

        Returns ``None`` if it doesn't exist.
        """
        address_type = command.get('address_type', u'msisdn')
        msisdn = command['msisdn']
        optout = yield self.optout_store_for_api(api).get_opt_out(
            address_type, msisdn)
        if optout is not None:
            returnValue(self.reply(command, success=True, opted_out=True,
                                   created_at=optout.created_at,
                                   message_id=optout.message))
        else:
            returnValue(self.reply(command, success=True, opted_out=False))
