# -*- test-case-name: go.apps.jsbox.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from twisted.internet.defer import inlineCallbacks

from vumi.application.sandbox import Sandbox, SandboxResource, SandboxCommand
from vumi.persist.txredis_manager import TxRedisManager
from vumi import log

from go.vumitools.api import VumiApiCommand
from go.vumitools.app_worker import GoApplicationMixin
from go.vumitools.middleware import DebitAccountMiddleware


class JsSandboxResource(SandboxResource):
    def sandbox_init(self, api):
        javascript = self.app_worker.javascript_for_sandbox(api.sandbox_id)
        api.sandbox_send(SandboxCommand(cmd="initialize",
                                        javascript=javascript))


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
        self.resources.add_resource("_js", JsSandboxResource(self.worker_name,
            self, self.config))

    @inlineCallbacks
    def setup_application(self):
        yield super(JsBoxApplication, self).setup_application()
        yield self._go_setup_application()

    @inlineCallbacks
    def teardown_application(self):
        yield super(JsBoxApplication, self).teardown_application()
        yield self._go_teardown_application()

    def javascript_for_sandbox(self, sandbox_id):
        return self.redis.get("#".join([self.r_prefix, sandbox_id]))

    # override selecting a sandbox id to retrieve id based on account name

    def _account_for_message(self, msg):
        return LookupAccountMiddleware.map_message_to_account_key(msg)

    def sandbox_id_for_message(self, msg):
        """Return the account  as the sandbox id."""
        return self._account_for_message(msg)

    def sandbox_id_for_event(self, event):
        """Return the account  as the sandbox id."""
        return self._account_for_message(event)

    # Vumi API command processing
    # TODO: refactor this out into common code somehow

    def consume_control_command(self, command_message):
        """
        Handle a VumiApiCommand message that has arrived.

        :type command_message: VumiApiCommand
        :param command_message:
            The command message received for this application.
        """
        cmd_method_name = 'process_command_%(command)s' % command_message
        args = command_message['args']
        kwargs = command_message['kwargs']
        cmd_method = getattr(self, cmd_method_name, None)
        if cmd_method:
            return cmd_method(*args, **kwargs)
        else:
            return self.process_unknown_cmd(cmd_method_name, )

    def process_unknown_cmd(self, method_name, *args, **kwargs):
        log.error("Unknown vumi API command: %s(%s, %s)" % (
            method_name, args, kwargs))

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):
        # TODO: this should use LookupAccountMiddleware as soon as that
        #       gets a map_payload_to_user function.
        account_key = DebitAccountMiddleware.map_payload_to_user(msg_options)
        log.info("Starting JsBox conversation for account %r (batch: %r)." %
                 (account_key, batch_id))
