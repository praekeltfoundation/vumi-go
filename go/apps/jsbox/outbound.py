# -*- test-case-name: go.apps.jsbox.tests.test_outbound -*-
# -*- coding: utf-8 -*-

"""Outbound message resource for JS Box sandboxes"""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.sandbox import OutboundResource
from vumi import log


class GoOutboundResource(OutboundResource):
    """Resource that provides outbound message support for Go."""

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
        yield self.app_worker.send_to(to_addr, content, **msg_options)

        returnValue(self.reply(command, success=True))

    def handle_send_to(self, api, command):
        # Generic sending is not supported in Vumi Go sandboxes
        return self.reply(command, success=False,
                          reason="Generic sending not supported in Vumi Go")
