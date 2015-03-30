# -*- test-case-name: go.apps.opt_out.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker
from go.vumitools.opt_out import OptOutStore


class OptOutApplication(GoApplicationWorker):

    worker_name = 'opt_out_application'

    @inlineCallbacks
    def consume_user_message(self, message):

        msg_mdh = self.get_metadata_helper(message)
        if not msg_mdh.has_user_account():
            # We don't have an account to opt out of.
            # Since this can only happen for redirected messages, assume we
            # aren't dealing with an API.
            yield self.reply_to(
                message, "Your opt-out was received but we failed to link it "
                "to a specific service, please try again later.")
            return

        account_key = yield msg_mdh.get_account_key()
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

    def process_command_start(self, cmd_id, user_account_key,
                              conversation_key):
        log.debug('OptOutApplication started: %s' % (conversation_key,))
        return super(OptOutApplication, self).process_command_start(
            cmd_id, user_account_key, conversation_key)
