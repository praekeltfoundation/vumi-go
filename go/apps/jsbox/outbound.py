# -*- test-case-name: go.apps.jsbox.tests.test_outbound -*-
# -*- coding: utf-8 -*-

"""Outbound message resource for JS Box sandboxes"""

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.sandbox import SandboxResource
from vumi import log


class GoOutboundResource(SandboxResource):
    """Resource that provides outbound message support for Go."""

    def _handle_reply(self, api, command, reply_func):
        if 'content' not in command:
            return succeed(self.reply(
                command, success=False,
                reason=u"'content' must be given in replies."))
        if 'in_reply_to' not in command:
            return succeed(self.reply(
                command, success=False,
                reason=u"'in_reply_to' must be given in replies."))
        orig_msg = api.get_inbound_message(command['in_reply_to'])
        if orig_msg is None:
            return succeed(self.reply(
                command, success=False, reason=u"Could not find original"
                " message with id: %r" % command['in_reply_to']))

        content = command['content']
        continue_session = command.get('continue_session', True)
        conv = self.app_worker.conversation_for_api(api)
        helper_metadata = conv.set_go_helper_metadata(
            orig_msg['helper_metadata'])

        d = reply_func(orig_msg, content, continue_session=continue_session,
                       helper_metadata=helper_metadata)
        d.addCallback(lambda r: self.reply(command, success=True))
        d.addErrback(lambda f: self.reply(command, success=False,
                                          reason=unicode(f.getErrorMessage())))
        return d

    def handle_reply_to(self, api, command):
        return self._handle_reply(api, command, self.app_worker.reply_to)

    def handle_reply_to_group(self, api, command):
        return self._handle_reply(api, command, self.app_worker.reply_to_group)

    @inlineCallbacks
    def handle_send_to_tag(self, api, command):
        tag = (command.get('tagpool'), command.get('tag'))
        content = command.get('content')
        to_addr = command.get('to_addr')
        if None in (tag[0], tag[1], content, to_addr):
            returnValue(self.reply(
                command, success=False,
                reason="Tag, content or to_addr not specified"))
        log.info("Sending outbound message to %r via tag %r, content: %r" %
                 (to_addr, tag, content))

        user_api = self.app_worker.user_api_for_api(api)
        tags = yield user_api.list_endpoints()
        if tag not in tags:
            returnValue(self.reply(command, success=False,
                                   reason="Tag %r not held by account"
                                   % (tag,)))
        msg_options = yield user_api.msg_options(tag)
        conv = self.app_worker.conversation_for_api(api)
        self.app_worker.add_conv_to_msg_options(conv, msg_options)
        endpoint = ':'.join(tag)
        yield self.app_worker.send_to(
            to_addr, content, endpoint=endpoint, **msg_options)

        returnValue(self.reply(command, success=True))
