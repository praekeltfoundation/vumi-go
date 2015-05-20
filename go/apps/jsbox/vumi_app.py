# -*- test-case-name: go.apps.jsbox.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

import logging

from twisted.internet.defer import inlineCallbacks

from vxsandbox import JsSandbox, SandboxResource

from vumi.config import ConfigDict
from vumi import log

from go.apps.jsbox.outbound import mk_inbound_push_trigger
from go.apps.jsbox.utils import jsbox_config_value, jsbox_js_config
from go.vumitools.app_worker import (
    GoApplicationMixin, GoApplicationConfigMixin)


class ConversationConfigResource(SandboxResource):
    """Resource that provides access to conversation config."""

    def handle_get(self, api, command):
        key = command.get("key")
        if key is None:
            return self.reply(command, success=False)
        conversation = self.app_worker.conversation_for_api(api)
        value = jsbox_config_value(conversation.config, key)
        return self.reply(command, value=value, success=True)


class JsBoxConfig(JsSandbox.CONFIG_CLASS, GoApplicationConfigMixin):
    jsbox_app_config = ConfigDict(
        "Custom configuration passed to the javascript code.", default={})
    jsbox = ConfigDict(
        "Must have 'javascript' field containing JavaScript code to run.")

    @property
    def javascript(self):
        if not self.jsbox:
            return None
        return self.jsbox['javascript']

    @property
    def sandbox_id(self):
        return self.conversation.user_account.key


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
        return api.config.conversation

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
            'mxit': 'mxit',
            'wechat': 'wechat',
        }.get(msg['transport_type'], 'sms')

    @inlineCallbacks
    def process_message_in_sandbox(self, msg):
        # TODO remove the delivery class inference and injection into the
        # message once we have message address types
        metadata = msg['helper_metadata']
        metadata['delivery_class'] = self.infer_delivery_class(msg)
        config = yield self.get_config(msg)
        if not config.javascript:
            log.warning("No JS for conversation: %s" % (
                config.conversation.key,))
            return
        yield super(JsBoxApplication, self).process_message_in_sandbox(msg)

    @inlineCallbacks
    def process_event_in_sandbox(self, event):
        """
        We only want to process events in the sandbox if configured to do so.
        """
        config = yield self.get_config(event)
        js_config = self.get_jsbox_js_config(config.conversation)
        if js_config is None:
            return
        if js_config.get('process_events'):
            yield super(JsBoxApplication, self).process_event_in_sandbox(event)
        else:
            api = self.create_sandbox_api(self.resources, config)
            log_msg = "Ignoring event for conversation: %s" % (
                config.conversation.key,)
            yield api.log(log_msg, logging.INFO)

    def process_command_start(self, cmd_id, user_account_key,
                              conversation_key):
        log.info("Starting javascript sandbox conversation (key: %r)." %
                 (conversation_key,))
        return super(JsBoxApplication, self).process_command_start(
            cmd_id, user_account_key, conversation_key)

    def send_inbound_push_trigger(self, to_addr, conversation):
        log.debug('Starting %r -> %s' % (conversation, to_addr))
        msg = mk_inbound_push_trigger(to_addr, conversation)
        return self.consume_user_message(msg)

    def get_jsbox_js_config(self, conv):
        try:
            return jsbox_js_config(conv.config)
        except Exception:
            log.err(
                "Bad jsbox js config: %s"
                % (jsbox_config_value(conv.config, 'config'),))
            return

    @inlineCallbacks
    def process_command_send_jsbox(self, cmd_id, user_account_key,
                                   conversation_key, batch_id):
        conv = yield self.get_conversation(user_account_key, conversation_key)
        js_config = self.get_jsbox_js_config(conv)
        if js_config is None:
            return
        delivery_class = js_config.get('delivery_class')

        if conv is None:
            log.warning("Cannot find conversation '%s' for user '%s'." % (
                conversation_key, user_account_key))
            return

        for contacts in (yield conv.get_opted_in_contact_bunches(
                delivery_class)):
            for contact in (yield contacts):
                to_addr = contact.addr_for(delivery_class)
                yield self.send_inbound_push_trigger(
                    to_addr, conv)
