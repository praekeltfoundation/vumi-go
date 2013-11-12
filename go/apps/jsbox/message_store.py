# -*- test-case-name: go.apps.jsbox.tests.test_messagestore -*-
# -*- coding: utf-8 -*-

"""
Resource for accessing information stored in Go's message store.
Allows for querying any conversation in a Go Account holder's account.
"""

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.sandbox import SandboxResource


def conversation_owner(func):
    @inlineCallbacks
    def wrapper(self, api, command):
        conversation_key = command.get('conversation_key')
        if conversation_key is None:
            conversation = self.app_worker.conversation_for_api(api)
        else:
            conversation = yield self.get_conversation(api, conversation_key)
            if conversation is None:
                returnValue(self.reply(
                    command, success=False,
                    reason='Invalid conversation_key'))

        resp = yield func(self, conversation, api, command)
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


class MessageStoreResource(SandboxResource):

    def get_user_api(self, api):
        return self.app_worker.user_api_for_api(api)

    def get_conversation(self, api, conversation_key):
        user_api = self.get_user_api(api)
        return user_api.get_wrapped_conversation(conversation_key)

    @conversation_owner
    def handle_progress_status(self, conversation, api, command):
        return self.reply(command, success=True,
                          progress_status=conversation.get_progress_status())
