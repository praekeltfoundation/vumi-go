# -*- test-case-name: go.apps.jsbox.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.config import ConfigDict
from vumi.application.sandbox import JsSandbox, SandboxResource
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin, GoWorkerConfigMixin


class ConversationConfigResource(SandboxResource):
    """Resource that provides access to conversation config."""

    def handle_get(self, api, command):
        key = command.get("key")
        if key is None:
            return self.reply(command, success=False)
        conversation = self.app_worker.conversation_for_api(api)
        app_config = conversation.config.get("jsbox_app_config", {})
        key_config = app_config.get(key, {})
        value = key_config.get('value')
        return self.reply(command, value=value, success=True)


class JsBoxConfig(JsSandbox.CONFIG_CLASS, GoWorkerConfigMixin):
    jsbox_app_config = ConfigDict(
        "Custom configuration passed to the javascript code.", default={})
    jsbox = ConfigDict(
        "Must have 'javascript' field containing JavaScript code to run.")

    @property
    def javascript(self):
        return self.jsbox['javascript']

    @property
    def sandbox_id(self):
        return self.get_conversation().user_account.key


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

    ALLOWED_ENDPOINTS = None
    CONFIG_CLASS = JsBoxConfig
    worker_name = 'jsbox_application'

    @inlineCallbacks
    def setup_application(self):
        yield super(JsBoxApplication, self).setup_application()
        yield self._go_setup_worker()

    @inlineCallbacks
    def teardown_application(self):
        yield super(JsBoxApplication, self).teardown_application()
        yield self._go_teardown_worker()

    def conversation_for_api(self, api):
        return api.config.get_conversation()

    def user_api_for_api(self, api):
        conv = self.conversation_for_api(api)
        return self.get_user_api(conv.user_account.key)

    def get_config(self, msg):
        return self.get_message_config(msg)

    def infer_delivery_class(self, msg):
        return {
            'smpp': 'sms',
            'sms': 'sms',
            'ussd': 'ussd',
            'twitter': 'twitter',
            'xmpp': 'gtalk',
        }.get(msg['transport_type'], 'sms')

    def process_message_in_sandbox(self, msg):
        # TODO remove the delivery class inference and injection into the
        # message once we have message address types
        metadata = msg['helper_metadata']
        metadata['delivery_class'] = self.infer_delivery_class(msg)
        return super(JsBoxApplication, self).process_message_in_sandbox(msg)

    def process_command_start(self, user_account_key, conversation_key):
        log.info("Starting javascript sandbox conversation (key: %r)." %
                 (conversation_key,))
        return super(JsBoxApplication, self).process_command_start(
            user_account_key, conversation_key)
