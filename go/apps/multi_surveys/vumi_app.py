# -*- test-case-name: go.apps.multi_surveys.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from vxpolls.multipoll_example import MultiPollApplication, EventPublisher
from vxpolls.manager import PollManager

from vumi.message import TransportUserMessage
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin, GoWorkerConfigMixin
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


class MultiSurveyConfig(MamaPollApplication.CONFIG_CLASS, GoWorkerConfigMixin):
    pass


class MultiSurveyApplication(MamaPollApplication, GoApplicationMixin):
    CONFIG_CLASS = MultiSurveyConfig

    worker_name = 'multi_survey_application'

    def validate_config(self):
        # vxpolls
        vxp_config = self.config.get('vxpolls', {})
        self.poll_prefix = vxp_config.get('prefix')

    @inlineCallbacks
    def setup_application(self):
        self.event_publisher = EventPublisher()

        yield self._go_setup_worker()
        self.pm = PollManager(self.redis, self.poll_prefix)

        self.event_publisher.subscribe('new_user', self.metric_event_handler)
        self.event_publisher.subscribe('new_registrant',
                                       self.metric_event_handler)
        self.event_publisher.subscribe('new_poll', self.metric_event_handler)
        self.event_publisher.subscribe('inbound_message',
                                       self.metric_event_handler)
        self.event_publisher.subscribe('outbound_message',
                                       self.metric_event_handler)
        self.event_publisher.subscribe('new_registrant',
                                       self.new_registrant_handler)

    @inlineCallbacks
    def incr_event_metric(self, event, metric_suffix):
        go = event.message['helper_metadata']['go']
        metric_name = "%s.%s.%s" % (
            go['user_account'], go['conversation_key'], metric_suffix)
        value = yield self.redis.incr(metric_name)
        self.publish_metric(metric_name, value)

    @inlineCallbacks
    def metric_event_handler(self, event):
        yield self.incr_event_metric(event, "%s_count" % event.event_type)

    @inlineCallbacks
    def new_registrant_handler(self, event):
        participant = event.participant
        hiv_messages = participant.get_label('HIV_MESSAGES')
        if hiv_messages == "1":
            # Wants HIV messages
            yield self.incr_event_metric(event, "hiv_registrant_count")
        else:
            # Wants STD messages
            yield self.incr_event_metric(event, "std_registrant_count")

    @inlineCallbacks
    def teardown_application(self):
        yield self.pm.stop()
        yield self._go_teardown_worker()

    def is_registered(self, participant):
        return participant.get_label('HIV_MESSAGES') is not None

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
        msg_mdh = self.get_metadata_helper(message)
        account_key = msg_mdh.get_account_key()

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
        conversation.set_go_helper_metadata(
            msg_options.setdefault('helper_metadata', {}))
        msg = TransportUserMessage(from_addr=to_addr, to_addr=from_addr,
                content='', **msg_options)

        return self.consume_user_message(msg)

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
