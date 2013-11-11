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
        Accepts an address_type and address_value and
        retrieves the opt-out entry for it.

        Returns ``None`` if it doesn't exist.
        """
        address_type = command['address_type']
        address_value = command['address_value']
        optout = yield self.optout_store_for_api(api).get_opt_out(
            address_type, address_value)
        if optout is not None:
            returnValue(self.reply(command, success=True, opted_out=True,
                                   created_at=optout.created_at,
                                   message_id=optout.message))
        else:
            returnValue(self.reply(command, success=True, opted_out=False))

    def handle_count(self, api, command):
        """
        Return a count of however many opt-outs there are
        """
        oos = self.optout_store_for_api(api)
        d = oos.count()
        d.addCallback(
            lambda count: self.reply(command, success=True, count=count))
        return d

    @inlineCallbacks
    def handle_optout(self, api, command):
        """
        Opt out an address_type, address_value combination
        """
        oos = self.optout_store_for_api(api)
        address_type = command['address_type']
        address_value = command['address_value']
        message_id = command['message_id']
        optout = yield oos.new_opt_out(address_type, address_value, message={
            'message_id': message_id,
        })
        returnValue(self.reply(command, success=True, opted_out=True,
                               created_at=optout.created_at,
                               message_id=optout.message))

    def handle_cancel_optout(self, api, command):
        """
        Cancel an opt-out, effectively opting an address_type & address_value
        combination back in.
        """
        oos = self.optout_store_for_api(api)
        address_type = command['address_type']
        address_value = command['address_value']
        d = oos.delete_opt_out(address_type, address_value)
        d.addCallback(
            lambda _: self.reply(command, success=True, opted_out=False))
        return d
