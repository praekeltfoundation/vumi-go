# -*- test-case-name: go.apps.jsbox.tests.test_outbound -*-
# -*- coding: utf-8 -*-

"""Outbound message resource for JS Box sandboxes"""

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.sandbox import SandboxResource
from vumi.message import TransportUserMessage
from vumi import log


INBOUND_PUSH_TRIGGER = "inbound_push_trigger"


def mk_inbound_push_trigger(to_addr, conversation):
    """
    Construct a dummy inbound message used to trigger a push of
    a new message from a sandbox application.
    """
    msg_options = {
        'transport_name': None,
        'transport_type': None,
        'helper_metadata': {},
        # mark this message as special so that it can be idenitified
        # if it accidentally ends up elsewhere.
        INBOUND_PUSH_TRIGGER: True,
    }
    conversation.set_go_helper_metadata(msg_options['helper_metadata'])

    # We reverse the to_addr & from_addr since we're faking input
    # from the client to start the survey.

    # This generates a fake message id that is then used in the
    # in_reply_to field of the outbound message. We filter these
    # replies out and convert them into sends in the outbound
    # resource below

    msg = TransportUserMessage(from_addr=to_addr, to_addr=None,
                               content=None, **msg_options)
    return msg


def is_inbound_push_trigger(msg):
    """
    Returns true if a message is a dummy inbound push trigger
    created by :func:`mk_inbound_push_trigger`.
    """
    return bool(msg.get(INBOUND_PUSH_TRIGGER, False))


class InvalidHelperMetadata(Exception):
    """
    Internal exception raised when a sandboxed application
    sends invalid helper_metadata.
    """


class GoOutboundResource(SandboxResource):
    """Resource that provides outbound message support for Go.

    Includes support for replying, replying to groups and sending
    messages via given tags.

    Configuration options:

    :param list allowed_helper_metadata:
        List of helper_metadata fields that may be set by sandboxed
        applications.
    """

    def setup(self):
        self._allowed_helper_metadata = set(
            self.config.get('allowed_helper_metadata', []))

    def _mkfail(self, command, reason):
        return self.reply(command, success=False, reason=reason)

    def _mkfaild(self, command, reason):
        return succeed(self._mkfail(command, reason))

    def _get_helper_metadata(self, command):
        """
        Get a legal helper_metadata dict from `command` or raise an
        InvalidHelperMetadata exception with a suitable message.
        """
        helper_metadata = command.get('helper_metadata')
        if helper_metadata in [None, {}]:
            # No helper metadata, so return an empty dict.
            return {}
        if not self._allowed_helper_metadata:
            raise InvalidHelperMetadata("'helper_metadata' is not allowed")
        if not isinstance(helper_metadata, dict):
            raise InvalidHelperMetadata(
                "'helper_metadata' must be object or null.")
        if any(key not in self._allowed_helper_metadata
               for key in helper_metadata.iterkeys()):
            raise InvalidHelperMetadata(
                "'helper_metadata' may only contain the following keys: %s"
                % ', '.join(sorted(self._allowed_helper_metadata)))
        # Anything we have left is valid.
        return helper_metadata

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
        try:
            cmd_helper_metadata = self._get_helper_metadata(command)
        except InvalidHelperMetadata as err:
            return self._mkfaild(command, reason=unicode(err))
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
        helper_metadata.update(cmd_helper_metadata)

        # convert replies to push triggers into ordinary sends
        if is_inbound_push_trigger(orig_msg):
            d = self.app_worker.send_to(orig_msg["from_addr"], content,
                                        helper_metadata=helper_metadata)
        else:
            d = reply_func(orig_msg, content,
                           continue_session=continue_session,
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
            - ``helper_metadata``: An object of additional helper metadata
              fields to include in the reply.

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
            - ``helper_metadata``: An object of additional helper metadata
              fields to include in the reply.

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

    def handle_send_to_endpoint(self, api, command):
        """
        Sends a message to a specified endpoint.

        Command fields:
            - ``content``: The body of the reply message.
            - ``to_addr``: The address of the recipient (e.g. an MSISDN).
            - ``endpoint``: The name of the endpoint to send the message via.
            - ``helper_metadata``: An object of additional helper metadata
              fields to include in the message being sent.

        Reply fields:
            - ``success``: ``true`` if the operation was successful, otherwise
              ``false``.

        Example:

        .. code-block:: javascript

            api.request(
                'outbound.send_to_endpoint',
                {content: 'Welcome!', to_addr: '+27831234567',
                 endpoint: 'sms'},
                function(reply) { api.log_info('Message sent: ' +
                                               reply.success); });
        """
        if not 'content' in command:
            return self._mkfaild(
                command, reason=u"'content' must be given in sends.")
        if not isinstance(command['content'], (unicode, type(None))):
            return self._mkfaild(
                command, reason=u"'content' must be unicode or null.")
        if not isinstance(command.get('endpoint'), unicode):
            return self._mkfaild(
                command, reason=u"'endpoint' must be given in sends.")
        if not isinstance(command.get('to_addr'), unicode):
            return self._mkfaild(
                command, reason=u"'to_addr' must be given in sends.")
        try:
            cmd_helper_metadata = self._get_helper_metadata(command)
        except InvalidHelperMetadata as err:
            return self._mkfaild(command, reason=unicode(err))

        endpoint = command['endpoint']
        content = command['content']
        to_addr = command['to_addr']

        conv = self.app_worker.conversation_for_api(api)
        if endpoint not in conv.extra_endpoints:
            return self._mkfaild(
                command, reason="Endpoint %r not configured" % (endpoint,))

        msg_options = {}
        self.app_worker.add_conv_to_msg_options(conv, msg_options)
        msg_options['helper_metadata'].update(cmd_helper_metadata)

        log.info("Sending outbound message to %r via endpoint %r, content: %r"
                 % (to_addr, endpoint, content))

        d = self.app_worker.send_to(
            to_addr, content, endpoint=endpoint, **msg_options)

        d.addCallback(lambda r: self.reply(command, success=True))
        d.addErrback(lambda f: self._mkfail(command,
                                            unicode(f.getErrorMessage())))
        return d
