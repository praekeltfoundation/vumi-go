# -*- test-case-name: go.apps.rapidsms.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi Go application worker for RapidSMS."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.rapidsms_relay import RapidSMSRelay
from vumi import log

from go.vumitools.app_worker import (
    GoApplicationMixin, GoApplicationConfigMixin, GoWorkerConfigData)


class RapidSMSConfig(RapidSMSRelay.CONFIG_CLASS, GoApplicationConfigMixin):
    pass


class RapidSMSApplication(GoApplicationMixin, RapidSMSRelay):

    CONFIG_CLASS = RapidSMSConfig

    worker_name = 'rapidsms_application'

    @inlineCallbacks
    def setup_application(self):
        yield super(RapidSMSApplication, self).setup_application()
        yield self._go_setup_worker()

    @inlineCallbacks
    def teardown_application(self):
        yield super(RapidSMSApplication, self).teardown_application()
        yield self._go_teardown_worker()

    def get_config_data_for_conversation(self, conversation):
        dynamic_config = conversation.config.get('rapidsms', {}).copy()
        dynamic_config["vumi_auth_method"] = "basic"
        dynamic_config["vumi_username"] = conversation.key
        auth_config = conversation.config.get('auth_tokens', {})
        api_tokens = auth_config.get("api_tokens", [])
        dynamic_config["vumi_password"] = api_tokens[0] if api_tokens else None
        return GoWorkerConfigData(self.config, dynamic_config)

    @inlineCallbacks
    def get_ctxt_config(self, ctxt):
        username = getattr(ctxt, 'username', None)
        if username is None:
            raise ValueError("No username provided for retrieving"
                             " RapidSMS conversation.")
        user_account_key, _, conversation_key = username.partition(":")
        conv = yield self.get_conversation(user_account_key, conversation_key)
        if conv is None:
            log.warning("Cannot find conversation '%s' for user '%s'." % (
                conversation_key, user_account_key))
            raise ValueError("No conversation found for retrieiving"
                             " RapidSMS configuration.")
        config = yield self.get_config_for_conversation(conv)
        returnValue(config)

    def get_config(self, msg, ctxt=None):
        if msg is not None:
            return self.get_message_config(msg)
        elif ctxt is not None:
            return self.get_ctxt_config(ctxt)
        else:
            raise ValueError("No msg or context provided for"
                             " retrieving a RapidSMS config.")

    def process_command_start(self, user_account_key, conversation_key):
        log.info("Starting RapidSMS conversation (key: %r)." %
                 (conversation_key,))
        return super(RapidSMSApplication, self).process_command_start(
            user_account_key, conversation_key)
