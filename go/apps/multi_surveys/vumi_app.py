# -*- test-case-name: go.apps.multi_surveys.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from vxpolls.multipoll_example import MultiPollApplication
from vxpolls.manager import PollManager

from vumi.message import TransportUserMessage
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin
from go.vumitools.opt_out import OptOutStore


def hacky_hack_hack(config):
    from vumi.persist.redis_manager import RedisManager
    hacked_config = config.copy()
    return RedisManager.from_config(dict(hacked_config))


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
        r_server = hacky_hack_hack(self.config.get('redis_manager'))
        self.pm = PollManager(r_server, self.poll_prefix)
        yield self._go_setup_application()

    @inlineCallbacks
    def teardown_application(self):
        yield self._go_teardown_application()
        self.pm.stop()

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
            opt_out = yield opt_out_store.delete_opt_out("msisdn", from_addr)
            print "#################"
            print repr(from_addr)
            print repr(account_key)
            print repr(opt_out)
            print "#################"
            if opt_out:
                # delete the opt-out
                yield opt_out_store.delete_opt_out("msisdn", from_addr)
                # archive the user record so they can start from scratch
                scope_id = message['helper_metadata'].get('poll_id', '')
                participant = yield self.pm.get_participant(scope_id, message.user())
                yield self.pm.archive(participant.scope_id, participant)

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
