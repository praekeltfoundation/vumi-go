# -*- test-case-name: go.apps.surveys.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from vxpolls.example import PollApplication
from vxpolls.manager import PollManager

from vumi.message import TransportUserMessage
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin, GoWorkerConfigMixin


class SurveyConfig(PollApplication.CONFIG_CLASS, GoWorkerConfigMixin):
    pass


class SurveyApplication(PollApplication, GoApplicationMixin):
    CONFIG_CLASS = SurveyConfig

    worker_name = 'survey_application'

    def validate_config(self):
        # vxpolls
        vxp_config = self.config.get('vxpolls', {})
        self.poll_prefix = vxp_config.get('prefix')

    @inlineCallbacks
    def setup_application(self):
        yield self._go_setup_worker()
        self.pm = PollManager(self.redis, self.poll_prefix)

    @inlineCallbacks
    def teardown_application(self):
        yield self.pm.stop()
        yield self._go_teardown_worker()

    @inlineCallbacks
    def consume_user_message(self, message):
        contact = yield self.get_contact_for_message(message, create=True)
        yield self._handle_survey_message(message, contact)

    @inlineCallbacks
    def _handle_survey_message(self, message, contact):
        helper_metadata = message['helper_metadata']
        go = helper_metadata.get('go')
        poll_id = 'poll-%s' % (go.get('conversation_key'),)
        helper_metadata['poll_id'] = poll_id

        participant = yield self.pm.get_participant(
            poll_id, message.user())

        poll = yield self.pm.get_poll_for_participant(poll_id, participant)
        if poll is None:
            yield self.reply_to(
                message, 'Service Unavailable. Please try again later.',
                continue_session=False)
            return

        config = yield self.pm.get_config(poll_id)
        for key in config.get('include_labels', []):
            value = contact.extra[key]
            if value and key not in participant.labels:
                participant.set_label(key, value)

        yield self.pm.save_participant(poll_id, participant)
        yield super(SurveyApplication, self).consume_user_message(message)

    def start_survey(self, to_addr, contact, conversation, **msg_options):
        log.debug('Starting %r -> %s' % (conversation, to_addr))

        # We reverse the to_addr & from_addr since we're faking input
        # from the client to start the survey.
        from_addr = msg_options.pop('from_addr')
        conversation.set_go_helper_metadata(
            msg_options.setdefault('helper_metadata', {}))
        msg = TransportUserMessage(from_addr=to_addr, to_addr=from_addr,
                                   content='', **msg_options)

        return self._handle_survey_message(msg, contact)

    @inlineCallbacks
    def end_session(self, participant, poll, message):
        # At the end of a session we want to store the user's responses
        # as dynamic values on the contact's record in the contact database.
        # This does that.
        contact = yield self.get_contact_for_message(message, create=True)

        # Clear previous answers from this poll
        possible_labels = [q.get('label') for q in poll.questions]
        for label in possible_labels:
            if (label is not None) and (label in contact.extra):
                del contact.extra[label]

        contact.extra.update(participant.labels)
        yield contact.save()

        yield self.pm.save_participant(poll.poll_id, participant)
        yield self.trigger_event(message, 'survey_completed', {
            'from_addr': message['from_addr'],
            'message_id': message['message_id'],
            'transport_type': message['transport_type'],
            'participant': participant.dump(),
        })
        yield super(SurveyApplication, self).end_session(
            participant, poll, message)

    @inlineCallbacks
    def process_command_send_survey(self, cmd_id, user_account_key,
                                    conversation_key, batch_id, msg_options,
                                    delivery_class, **extra_params):

        conv = yield self.get_conversation(user_account_key, conversation_key)

        if conv is None:
            log.warning("Cannot find conversation '%s' for user '%s'." % (
                conversation_key, user_account_key))
            return

        for contacts in (yield conv.get_opted_in_contact_bunches(
                delivery_class)):
            for contact in (yield contacts):
                to_addr = contact.addr_for(delivery_class)
                # Set some fake msg_options in case we didn't get real ones.
                msg_options.setdefault('from_addr', None)
                msg_options.setdefault('transport_name', None)
                msg_options.setdefault('transport_type', 'sms')
                yield self.start_survey(to_addr, contact, conv, **msg_options)
