# -*- test-case-name: go.apps.opt_out.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker
from go.vumitools.opt_out import OptOutStore


class OptOutApplication(GoApplicationWorker):

    @inlineCallbacks
    def consume_user_message(self, message):

        helper_metadata = message.get('helper_metadata', {})
        go_metadata = helper_metadata.get('go', {})
        account_key = go_metadata.get('user_account', None)

        if account_key is None:
            # We don't have an account to opt out of.
            # Since this can only happen for redirected messages, assume we
            # aren't dealing with an API.
            yield self.reply_to(
                message, "Your opt-out was received but we failed to link it "
                "to a specific service, please try again later.")
            return

        opt_out_store = OptOutStore(self.manager, account_key)
        from_addr = message.get("from_addr")
        # Note: for now we are hardcoding addr_type as 'msisdn'
        # as only msisdn's are opting out currently
        yield opt_out_store.new_opt_out("msisdn", from_addr, message)

        if message.get('transport_type') == 'http_api':
            yield self.reply_to(
                message, '{"msisdn":"%s","opted_in": false}' % (from_addr,))
        else:
            yield self.reply_to(message, "You have opted out")

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):

        if is_client_initiated:
            log.debug('Conversation %r is client initiated, no need to notify '
                'the application worker' % (conversation_key,))
            return

        conv = yield self.get_conversation(batch_id, conversation_key)

        to_addresses = yield conv.get_contacts_addresses()
        for to_addr in to_addresses:
            # XXX: !?!?
            # I guess this never gets run.
            yield self.start_survey(to_addr, conv, **msg_options)
