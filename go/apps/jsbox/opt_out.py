# -*- test-case-name: go.apps.jsbox.tests.test_opt_out -*-
# -*- coding: utf-8 -*-

"""Resource for accessing and modifying a contact's opt-out/opt-in
   status from the sandbox"""

from functools import wraps

from twisted.internet.defer import inlineCallbacks, returnValue

from vxsandbox import SandboxResource


def optout_authorized(func):
    @wraps(func)
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
        @wraps(func)
        def wrapper(self, api, command):
            for key in keys:
                if key not in command:
                    return self.reply(command, success=False,
                                      reason='Missing key: %s' % (key,))

                value = command[key]
                # NOTE: This needs to be updated once we have some proper
                #       tools for validating command input
                # value is not allowed to be `False`, `None`, `0`
                # or an empty string.
                if not value:
                    return self.reply(
                        command, success=False,
                        reason='Invalid value "%s" for "%s"' % (value, key))

            return func(self, api, command)
        return wrapper
    return decorator


class OptOutResource(SandboxResource):

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

        Command fields:
            - ``address_type``: the type of address to check for opt-out
              status on. At the moment only ``msisdn`` is used.
            - ``address_value``: the value of the ``address_type`` to check.
              At the moment this would be a normalized msisdn.

        Success reply fields:
            - ``success``: set to ``true``
            - ``opted_out``: set to ``true`` or ``false``
            - ``created_at``: the timestamp of the opt-out (if opted out)
            - ``message_id``: the message_id of the message that triggered
              the opt-out.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.
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

        Command fields: None

        Success reply fields:
            - ``success``: set to ``true``
            - ``count``: an Integer.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

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

        Command fields:
            - ``address_type``: the type of address to opt-out.
              At the moment only ``msisdn`` is used.
            - ``address_value``: the value of the ``address_type`` to opt-out.
            - ``message_id`` the message_id of the message that triggered
              the opt-out, for auditing purposes.

        Success reply fields:
            - ``success``: set to ``true``
            - ``opted_out``: set to ``true``
            - ``created_at``: the timestamp of the opt-out
            - ``message_id``: the message_id of the message that triggered
              the opt-out.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

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

        Command fields:
            - ``address_type``: the type of address cancel the opt-out for.
            - ``address_value``: the value of the ``address_type`` to cancel
              the opt-out for.

        Success reply fields:
            - ``success``: set to ``true``
            - ``opted_out``: set to ``false``

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

        """
        oos = self.optout_store_for_api(api)
        address_type = command['address_type']
        address_value = command['address_value']
        d = oos.delete_opt_out(address_type, address_value)
        d.addCallback(
            lambda _: self.reply(command, success=True, opted_out=False))
        return d
