# -*- test-case-name: go.apps.jsbox.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.sandbox import JsSandbox, SandboxResource
from vumi.message import TransportEvent
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin


class ConversationConfigResource(SandboxResource):
    """Resource that provides access to conversation config."""

    def handle_get(self, api, command):
        key = command.get("key")
        if key is None:
            return self.reply(command, success=False)
        conversation = self.app_worker.conversation_for_api(api)
        app_config = conversation.metadata.get("jsbox_app_config", {})
        key_config = app_config.get(key, {})
        value = key_config.get('value')
        return self.reply(command, value=value, success=True)


class JsBoxApplication(GoApplicationMixin, JsSandbox):
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

    And those from :class:`vumi.application.sandbox.JsSandbox`.
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

    def javascript_for_api(self, api):
        return api.javascript

    def conversation_for_api(self, api):
        return api.conversation

    def user_api_for_api(self, api):
        return self.get_user_api(api.conversation.user_account.key)

    @inlineCallbacks
    def sandbox_protocol_for_message(self, msg_or_event):
        """Return a sandbox protocol for a message or event.

        Overrides method from :class:`Sandbox`.
        """
        if isinstance(msg_or_event, TransportEvent):
            msg = yield self.find_message_for_event(msg_or_event)
        else:
            msg = msg_or_event

        metadata = self.get_go_metadata(msg)
        sandbox_id = yield metadata.get_account_key()
        conversation = yield metadata.get_conversation()
        config = conversation.metadata['jsbox']
        javascript = config['javascript']
        api = self.create_sandbox_api(self.resources)
        api.javascript = javascript
        api.conversation = conversation
        protocol = self.create_sandbox_protocol(sandbox_id, api)
        returnValue(protocol)

    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):
        log.info("Starting javascript sandbox conversation (key: %r)." %
                 (conversation_key,))
