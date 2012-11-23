# -*- test-case-name: go.apps.jsbox.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.sandbox import Sandbox, JsSandboxResource
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin
from go.vumitools.middleware import DebitAccountMiddleware


class JsBoxApplication(GoApplicationMixin, Sandbox):
    """
    Application that processes message in a Node.js Javascript Sandbox.

    The Javascript is supplied by a conversation given by the user.

    Configuration parameters:

    :param str worker_name:
        The name of this worker, used for receiving control messages.
    :param dict message_store:
        Message store configuration.
    :param dict api_routing:
        Vumi API command routing information (optional).
    """

    SEND_TO_TAGS = frozenset(['default'])
    worker_name = 'jsbox_application'

    def validate_config(self):
        super(JsBoxApplication, self).validate_config()
        self._go_validate_config()

    @inlineCallbacks
    def setup_application(self):
        yield super(JsBoxApplication, self).setup_application()
        yield self._go_setup_application()

    @inlineCallbacks
    def teardown_application(self):
        yield super(JsBoxApplication, self).teardown_application()
        yield self._go_teardown_application()

    @inlineCallbacks
    def sandbox_protocol_for_message(self, msg_or_event):
        """Return a sandbox protocol for a message or event.

        Overrides method from :class:`Sandbox`.
        """
        metadata = self.get_go_metadata(msg_or_event)
        sandbox_id = metadata.get_account_key()
        conversation = yield metadata.get_conversation()
        config = conversation.metadata['jsbox']
        javascript = JsSandboxResource(
            self.worker_name, self, {'javascript': config['javascript']})
        resources = self.resources.copy()
        resources.add_resource("_js", javascript)
        api = self.create_sandbox_api(resources)
        protocol = self.create_sandbox_protocol(sandbox_id, api)
        returnValue(protocol)

    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):
        log.info("Starting javascript sandbox conversation (key: %r)." %
                 (conversation_key,))
