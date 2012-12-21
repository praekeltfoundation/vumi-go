# -*- test-case-name: go.apps.jsbox.tests.test_outbound -*-
# -*- coding: utf-8 -*-

"""Outbound message resource for JS Box sandboxes"""

from vumi.application.sandbox import OutboundResource
from vumi import log


class GoOutboundResource(OutboundResource):
    """Resource that provides outbound message support for Go."""

    def handle_send_to_tag(self, api, command):
        tagpool = command.get('tagpool')
        tag = command.get('tag')
        content = command['content']
        to_addr = command['to_addr']
        # TODO: check tagpool / tag is owned by an active conversation
        # TODO: fetch tagpool metadata for tagpool
        msg_options = {}
        self.app_worker.send_to(to_addr, content, **msg_options)

    def handle_send_to(self, api, command):
        # Generic sending is not supported in Vumi Go sandboxes
        return self.reply(command, success=False,
                          reason="Generic sending not supported in Vumi Go")
