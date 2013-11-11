# -*- test-case-name: go.apps.jsbox.tests.test_optout -*-
# -*- coding: utf-8 -*-

"""Resource for accessing and modifying a contact's opt-out/opt-in
   status from the sandbox"""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.sandbox import SandboxResource


class OptoutException(Exception):
    pass


def optout_authorized(func):
    @inlineCallbacks
    def wrapper(self, api, command):
        if not (yield self.is_allowed(api)):
            returnValue(self.reply(
                command, success=False,
                reason='Account not allowed to manage optouts.'))

        resp = yield func(self, api, command)
        returnValue(resp)
    return wrapper


def ensure_params(*keys):
    def decorator(func):
        def wrapper(self, api, command):
            for key in keys:
                if key not in command:
                    return self.reply(command, success=False,
                                      reason='Missing key: %s' % (key,))

                value = command[key]
                # value is not allowed to be `False`, `None` or an empty
                # string.
                if not value:
                    return self.reply(
                        command, success=False,
                        reason='Invalid value "%s" for "%s"' % (value, key))

            return func(self, api, command)
        return wrapper
    return decorator


class OptoutResource(SandboxResource):

    def get_user_api(self, api):
        return self.app_worker.user_api_for_api(api)

    def optout_store_for_api(self, api):
        return self.get_user_api(api).optout_store

    def is_allowed(self, api):
        user_api = self.get_user_api(api)
        d = user_api.get_user_account()
        d.addCallback(lambda account: account.can_manage_optouts)
        return d

    @ensure_params('address_type', 'address_value')
    @optout_authorized
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

    @optout_authorized
    def handle_count(self, api, command):
        """
        Return a count of however many opt-outs there are
        """
        oos = self.optout_store_for_api(api)
        d = oos.count()
        d.addCallback(
            lambda count: self.reply(command, success=True, count=count))
        return d

    @ensure_params('address_type', 'address_value', 'message_id')
    @optout_authorized
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

    @ensure_params('address_type', 'address_value')
    @optout_authorized
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
