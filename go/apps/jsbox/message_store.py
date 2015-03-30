# -*- test-case-name: go.apps.jsbox.tests.test_message_store -*-
# -*- coding: utf-8 -*-

"""
Resource for accessing information stored in Go's message store.
Allows for querying any conversation in a Go Account holder's account.
"""

from functools import wraps

from twisted.internet.defer import inlineCallbacks, returnValue

from vxsandbox import SandboxResource


def conversation_owner(func):
    @wraps(func)
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


class MessageStoreResource(SandboxResource):

    def get_user_api(self, api):
        return self.app_worker.user_api_for_api(api)

    def get_conversation(self, api, conversation_key):
        user_api = self.get_user_api(api)
        return user_api.get_wrapped_conversation(conversation_key)

    @conversation_owner
    @inlineCallbacks
    def handle_progress_status(self, conversation, api, command):
        """
        Accepts a conversation_key and retrieves the progress_status
        breakdown for that conversation.

        If no conversation is specified then the current application's
        conversation is used.

        Command fields:
            - ``conversation_key``: The key of the conversation to use.
              This is optional, if not specified the application's own
              conversation is used.

        Success reply fields:
            - ``success``: set to ``true``
            - ``progress_status``: A dictionary with a break down of the
              conversations progress status:

            .. code-block:: javascript

                {
                    'ack': 1,
                    'delivery_report': 0,
                    'delivery_report_delivered': 0,
                    'delivery_report_failed': 0,
                    'delivery_report_pending': 0,
                    'nack': 0,
                    'sent': 1,
                }

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.
        """
        status = yield conversation.get_progress_status()
        returnValue(self.reply(command, success=True,
                               progress_status=status))

    @conversation_owner
    @inlineCallbacks
    def handle_count_replies(self, conversation, api, command):
        """
        Count how many messages were received in the conversation.

        If no conversation is specified then the current application's
        conversation is used.

        Command fields:
            - ``conversation_key``: The key of the conversation to use.
              This is optional, if not specified the application's own
              conversation is used.

        Success reply fields:
            - ``success``: set to ``true``
            - ``count``: the number of messages received

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

        """
        count = yield conversation.count_inbound_messages()
        returnValue(self.reply(command, success=True, count=count))

    @conversation_owner
    @inlineCallbacks
    def handle_count_sent_messages(self, conversation, api, command):
        """
        Count how many messages were sent in the conversation.

        If no conversation is specified then the current application's
        conversation is used.

        Command fields:
            - ``conversation_key``: The key of the conversation to use.
              This is optional, if not specified the application's own
              conversation is used.

        Success reply fields:
            - ``success``: set to ``true``
            - ``count``: the number of messages sent

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

        """
        count = yield conversation.count_outbound_messages()
        returnValue(self.reply(command, success=True, count=count))

    @conversation_owner
    @inlineCallbacks
    def handle_count_inbound_uniques(self, conversation, api, command):
        """
        Count from how many unique "from_addr"s messages were received.

        If no conversation is specified then the current application's
        conversation is used.

        Command fields:
            - ``conversation_key``: The key of the conversation to use.
              This is optional, if not specified the application's own
              conversation is used.

        Success reply fields:
            - ``success``: set to ``true``
            - ``count``: the number of unique "from_addr"s messages
              were sent.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

        """
        count = yield conversation.count_inbound_uniques()
        returnValue(self.reply(command, success=True, count=count))

    @conversation_owner
    @inlineCallbacks
    def handle_count_outbound_uniques(self, conversation, api, command):
        """
        Count to how many unique "to_addr"s messages were sent.

        If no conversation is specified then the current application's
        conversation is used.

        Command fields:
            - ``conversation_key``: The key of the conversation to use.
              This is optional, if not specified the application's own
              conversation is used.

        Success reply fields:
            - ``success``: set to ``true``
            - ``count``: the number of unique "to_addrs"s messages
              were sent.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

        """
        count = yield conversation.count_outbound_uniques()
        returnValue(self.reply(command, success=True, count=count))

    @conversation_owner
    @inlineCallbacks
    def handle_inbound_throughput(self, conversation, api, command):
        """
        Count how many messages a minute were received.

        If no conversation is specified then the current application's
        conversation is used.

        Command fields:
            - ``conversation_key``: The key of the conversation to use.
              This is optional, if not specified the application's own
              conversation is used.
            - ``sample_time``: How far to look back to calculate the
              throughput. Defaults to 300 seconds (5 minutes)


        Success reply fields:
            - ``success``: set to ``true``
            - ``throughput``: how many inbound messages per minute the
              conversation has done on average.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

        """
        sample_time = int(command.get('sample_time', 300))
        throughput = yield conversation.get_inbound_throughput(sample_time)
        returnValue(self.reply(command, success=True, throughput=throughput))

    @conversation_owner
    @inlineCallbacks
    def handle_outbound_throughput(self, conversation, api, command):
        """
        Count how many messages a minute were sent.

        If no conversation is specified then the current application's
        conversation is used.

        Command fields:
            - ``conversation_key``: The key of the conversation to use.
              This is optional, if not specified the application's own
              conversation is used.
            - ``sample_time``: How far to look back to calculate the
              throughput. Defaults to 300 seconds (5 minutes)


        Success reply fields:
            - ``success``: set to ``true``
            - ``throughput``: how many outbound messages per minute the
              conversation has done on average.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure.

        """
        sample_time = int(command.get('sample_time', 300))
        throughput = yield conversation.get_outbound_throughput(sample_time)
        returnValue(self.reply(command, success=True, throughput=throughput))
