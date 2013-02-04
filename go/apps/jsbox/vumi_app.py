# -*- test-case-name: go.apps.jsbox.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.config import ConfigField
from vumi.application.sandbox import JsSandbox, SandboxResource
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


class JsBoxConfig(JsSandbox.CONFIG_CLASS):
    conversation = ConfigField("Conversation object from message.")
    javascript = ConfigField("Javascript from message.")


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

    CONFIG_CLASS = JsBoxConfig
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

    def get_conversation_config(self, conversation):
        config = conversation.metadata['jsbox'].copy()
        config['sandbox_id'] = conversation.user_account.key
        return config

    def get_config(self, msg):
        return self.get_message_config(msg)

    def sandbox_protocol_for_message(self, msg, config):
        """Return a sandbox protocol for a message or event.

        Overrides method from :class:`Sandbox`.
        """
        api = self.create_sandbox_api(self.resources)
        api.javascript = config.javascript
        api.conversation = config.conversation
        protocol = self.create_sandbox_protocol(api, config)
        return protocol

    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):
        log.info("Starting javascript sandbox conversation (key: %r)." %
                 (conversation_key,))
