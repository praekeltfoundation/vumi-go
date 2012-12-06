# -*- test-case-name: go.apps.multi_surveys.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from vxpolls.multipoll_example import MultiPollApplication
from vxpolls.manager import PollManager

from vumi.message import TransportUserMessage
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin
from go.vumitools.opt_out import OptOutStore


class MamaPollApplication(MultiPollApplication):
    registration_partial_response = "Please dial back in to " \
                                    "complete registration."
    registration_completed_response = "You have completed the " \
                                        "registration questions."
    batch_completed_response = "Please dial in again to " \
                                "complete the rest of this weeks questions."
    survey_completed_response = "You've done this week's 2 quiz questions. " \
                                "Please dial *120*2112# again next " \
                                "week for new questions. Stay well! " \
                                "Visit askmama.mobi"


class MultiSurveyApplication(MamaPollApplication, GoApplicationMixin):

    worker_name = 'multi_survey_application'

    def validate_config(self):
        self._go_validate_config()
        # vxpolls
        vxp_config = self.config.get('vxpolls', {})
        self.poll_prefix = vxp_config.get('prefix')

    @inlineCallbacks
    def setup_application(self):
        yield self._go_setup_application()
        self.pm = PollManager(self.redis, self.poll_prefix)

    @inlineCallbacks
    def teardown_application(self):
        yield self.pm.stop()
        yield self._go_teardown_application()

    @inlineCallbacks
    def consume_user_message(self, message):
        helper_metadata = message['helper_metadata']
        go = helper_metadata.get('go')
        helper_metadata['poll_id'] = 'poll-%s' % (
            go.get('conversation_key'),)

        # It is possible the user is opted-out
        # For the current use case (USSD sign-ups) we can
        # now assume that if someone is dialing back in they
        # want to register, therefore we can delete the opt-out
        gmt = self.get_go_metadata(message)
        account_key = yield gmt.get_account_key()

        if account_key is not None:
            # check if user is opted out
            opt_out_store = OptOutStore(self.manager, account_key)
            from_addr = message.get("from_addr")
            opt_out = yield opt_out_store.get_opt_out("msisdn", from_addr)
            if opt_out:
                # delete the opt-out
                yield opt_out_store.delete_opt_out("msisdn", from_addr)
                # archive the user record so they can start from scratch
                participant = yield self.pm.get_participant(
                                                helper_metadata['poll_id'],
                                                message.user())
                yield self.pm.archive(helper_metadata['poll_id'], participant)
        else:
            log.error("Could not find account_key for: %s" % (message))

        super(MultiSurveyApplication, self).consume_user_message(message)

    def start_survey(self, to_addr, conversation, **msg_options):
        log.debug('Starting %r -> %s' % (conversation, to_addr))

        # We reverse the to_addr & from_addr since we're faking input
        # from the client to start the survey.
        from_addr = msg_options.pop('from_addr')
        msg = TransportUserMessage(from_addr=to_addr, to_addr=from_addr,
                content='', **msg_options)

        gmt = self.get_go_metadata(msg)
        gmt.set_conversation_info(conversation)

        self.consume_user_message(msg)

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):

        if is_client_initiated:
            log.debug('Conversation %r is client initiated, no need to notify '
                'the application worker' % (conversation_key,))
            return

        conv = yield self.get_conversation(batch_id, conversation_key)

        for contacts in (yield conv.get_opted_in_contact_bunches()):
            for contact in (yield contacts):
                to_addr = contact.addr_for(conv.delivery_class)
                yield self.start_survey(to_addr, conv, **msg_options)

    @inlineCallbacks
    def collect_metrics(self, user_api, conversation_key):
        conv = yield user_api.get_wrapped_conversation(conversation_key)
        yield self.collect_message_metrics(conv)

    @inlineCallbacks
    def collect_message_metrics(self, conversation):
        sent = 0
        received = 0
        regispered = 0
        for batch_id in conversation.batches.keys():
            sent += yield self.vumi_api.mdb.batch_outbound_count(batch_id)
            received += yield self.vumi_api.mdb.batch_inbound_count(batch_id)

        self.publish_conversation_metric(
            conversation, 'messages_sent', sent)
        self.publish_conversation_metric(
            conversation, 'messages_received', received)
