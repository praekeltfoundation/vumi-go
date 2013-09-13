# -*- test-case-name: go.apps.jsbox.tests.test_outbound -*-
# -*- coding: utf-8 -*-

"""Outbound message resource for JS Box sandboxes"""

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.sandbox import SandboxResource
from vumi import log


class GoOutboundResource(SandboxResource):
    """Resource that provides outbound message support for Go.

    Includes support for replying, replying to groups and sending
    messages via given tags.
    """

    def _mkfail(self, command, reason):
        return self.reply(command, success=False, reason=reason)

    def _mkfaild(self, command, reason):
        return succeed(self._mkfail(command, reason))

    def _handle_reply(self, api, command, reply_func):
        if not 'content' in command:
            return self._mkfaild(
                command, reason=u"'content' must be given in replies.")
        if not isinstance(command['content'], (unicode, type(None))):
            return self._mkfaild(
                command, reason=u"'content' must be unicode or null.")
        if not isinstance(command.get('in_reply_to'), unicode):
            return self._mkfaild(
                command, reason=u"'in_reply_to' must be given in replies.")
        if command.get('continue_session', True) not in (True, False):
            return self._mkfaild(
                command, reason=u"'continue_session' must be either true or"
                " false if given")
        orig_msg = api.get_inbound_message(command['in_reply_to'])
        if orig_msg is None:
            return self._mkfaild(
                command, reason=u"Could not find original message with id: %r"
                % command['in_reply_to'])

        content = command['content']
        continue_session = command.get('continue_session', True)
        conv = self.app_worker.conversation_for_api(api)
        helper_metadata = conv.set_go_helper_metadata(
            orig_msg['helper_metadata'])

        d = reply_func(orig_msg, content, continue_session=continue_session,
                       helper_metadata=helper_metadata)
        d.addCallback(lambda r: self.reply(command, success=True))
        d.addErrback(lambda f: self._mkfail(command,
                                            unicode(f.getErrorMessage())))
        return d

    def handle_reply_to(self, api, command):
        """
        Sends a reply to the individual who sent a received message.

        Command fields:
            - ``content``: The body of the reply message.
            - ``in_reply_to``: The ``message id`` of the message being replied
              to.
            - ``continue_session``: Whether to continue the session (if any).
              Defaults to ``true``.

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
              ``false``.

        Example:

        .. code-block:: javascript

            api.request(
                'outbound.reply_to',
                {content: 'Welcome!',
                 in_reply_to: '06233d4eede945a3803bf9f3b78069ec'},
                function(reply) { api.log_info('Reply sent: ' +
                                               reply.success); });
        """
        return self._handle_reply(api, command, self.app_worker.reply_to)

    def handle_reply_to_group(self, api, command):
        """
        Sends a reply to the group from which a received message was sent.

        Command fields:
            - ``content``: The body of the reply message.
            - ``in_reply_to``: The ``message id`` of the message being replied
              to.
            - ``continue_session``: Whether to continue the session (if any).
              Defaults to ``true``.

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
              ``false``.

        Example:

        .. code-block:: javascript

            api.request(
                'outbound.reply_to_group',
                {content: 'Welcome!',
                 in_reply_to: '06233d4eede945a3803bf9f3b78069ec'},
                function(reply) { api.log_info('Reply to group sent: ' +
                                               reply.success); });
        """
        return self._handle_reply(api, command, self.app_worker.reply_to_group)

    @inlineCallbacks
    def handle_send_to_tag(self, api, command):
        """
        Sends a message to a specified tag.

        Command fields:
            - ``content``: The body of the reply message.
            - ``to_addr``: The address of the recipient (e.g. an MSISDN).
            - ``tagpool``: The name of the tagpool to send the message via.
            - ``tag``: The name of the tag (within the tagpool) to send the
              message from. Your Go user account must have the tag acquired.

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
              ``false``.

        Example:

        .. code-block:: javascript

            api.request(
                'outbound.send_to_tag',
                {content: 'Welcome!', to_addr: '+27831234567',
                 tagpool: 'vumi_long', tag: 'default10001'},
                function(reply) { api.log_info('Message sent: ' +
                                               reply.success); });
        """
        tag = (command.get('tagpool'), command.get('tag'))
        content = command.get('content')
        to_addr = command.get('to_addr')
        if any(not isinstance(u, unicode)
               for u in (tag[0], tag[1], content, to_addr)):
            returnValue(self._mkfail(
                command, reason="Tag, content or to_addr not specified"))
        log.info("Sending outbound message to %r via tag %r, content: %r" %
                 (to_addr, tag, content))

        conv = self.app_worker.conversation_for_api(api)
        tags = [tuple(endpoint.split(":", 1))
                for endpoint in conv.extra_endpoints]
        if tag not in tags:
            returnValue(self._mkfail(
                command, reason="Tag %r not held by account" % (tag,)))

        msg_options = {}
        self.app_worker.add_conv_to_msg_options(conv, msg_options)
        endpoint = ':'.join(tag)
        yield self.app_worker.send_to(
            to_addr, content, endpoint=endpoint, **msg_options)

        returnValue(self.reply(command, success=True))
