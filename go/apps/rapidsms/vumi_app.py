# -*- test-case-name: go.apps.rapidsms.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi Go application worker for RapidSMS."""

from twisted.internet.defer import inlineCallbacks

from vumi.applications.rapidsms_relay import RapidSMSRelay, RapidSMSRelayConfig
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin, GoWorkerConfigMixin


class RapidSMSConfig(GoWorkerConfigMixin, RapidSMSRelayConfig):

    @property
    def vumi_username(self):
        conv = self.get_conversation()
        return conv.key

    @property
    def vumi_password(self):
        conv = self.get_conversation()
        api_tokens = conv.config.get("api_tokens", [])
        return api_tokens[0] if api_tokens else None

    @property
    def vumi_auth_method(self):
        return "basic"


class RapidSMSApplication(GoApplicationMixin, RapidSMSRelay):
    worker_name = 'rapidsms_application'

    @inlineCallbacks
    def setup_application(self):
        yield super(RapidSMSApplication, self).setup_application()
        yield self._go_setup_worker()

    @inlineCallbacks
    def teardown_application(self):
        yield super(RapidSMSApplication, self).teardown_application()
        yield self._go_teardown_worker()

    def get_config(self, msg):
        return self.get_message_config(msg)

    def process_command_start(self, user_account_key, conversation_key):
        log.info("Starting RapidSMS conversation (key: %r)." %
                 (conversation_key,))
        return super(RapidSMSApplication, self).process_command_start(
            user_account_key, conversation_key)
