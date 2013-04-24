# -*- test-case-name: go.apps.surveys.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks, returnValue
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
        helper_metadata = message['helper_metadata']
        go = helper_metadata.get('go')
        poll_id = 'poll-%s' % (go.get('conversation_key'),)
        helper_metadata['poll_id'] = poll_id

        # If we've found a contact, grab it's dynamic-extra values
        # and update the participant with those before sending it
        # to the PollApplication
        contact = yield self.get_contact_for_message(message)
        if contact:
            participant = yield self.pm.get_participant(
                poll_id, message.user())
            config = yield self.pm.get_config(poll_id)
            for key in config.get('include_labels', []):
                value = contact.extra[key]
                if value and key not in participant.labels:
                    participant.set_label(key, value)

            # NOTE:
            #
            # This is here because our SMS opt-out and our USSD opt-out's
            # are not linked properly. Some bits and pieces are missing.
            # The USSD opt-out happens through variables set in the
            # contacts.extras[] dict, but the SMS is set in the contact_store.
            # The USSD opt-out is fed back to the SMS/contact_store via
            # the event handlers (specifically sna/handlers.py) and this
            # hack links it the other way around again. We need the SMS
            # contact_store opt-out status back to the participant's variables
            # that vxpolls knows about.
            #
            # account_key = go.get('user_account')
            # print 'account_key', account_key
            # if account_key:
            #     user_api = self.get_user_api(account_key)
            #     contact_store = user_api.contact_store
            #     is_opted_out = yield contact_store.contact_has_opted_out(
            #         contact)
            #     print 'participant', participant
            #     if is_opted_out:
            #         print '--- is opted out'
            #         participant.set_label('opted_out', '2')
            #         print 'opt-out set'
            #         print participant.dump()
            #     else:
            #         print '--- is NOT opted out'

            yield self.pm.save_participant(poll_id, participant)

        yield super(SurveyApplication, self).consume_user_message(message)

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
    def end_session(self, participant, poll, message):
        # At the end of a session we want to store the user's responses
        # as dynamic values on the contact's record in the contact database.
        # This does that.
        contact = yield self.get_contact_for_message(message)
        if contact:
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
        yield super(SurveyApplication, self).end_session(participant, poll,
            message)

    @inlineCallbacks
    def get_conversation(self, batch_id, conversation_key):
        batch = yield self.vumi_api.mdb.get_batch(batch_id)
        if batch is None:
            log.error('Cannot find batch for batch_id %s' % (batch_id,))
            return

        user_account_key = batch.metadata["user_account"]
        if user_account_key is None:
            log.error("No account key in batch metadata: %r" % (batch,))
            return

        user_api = self.get_user_api(user_account_key)
        conv = yield user_api.get_wrapped_conversation(conversation_key)
        returnValue(conv)

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):

        if is_client_initiated:
            log.debug('Conversation %r is client initiated, no need to notify '
                      'the application worker' % (conversation_key,))
            return

        conv = yield self.get_conversation(batch_id, conversation_key)
        if not conv:
            return

        for contacts in (yield conv.get_opted_in_contact_bunches()):
            for contact in (yield contacts):
                to_addr = contact.addr_for(conv.delivery_class)
                yield self.start_survey(to_addr, conv, **msg_options)

    @inlineCallbacks
    def process_command_send_message(self, *args, **kwargs):
        log.info('Processing send_message: %s' % kwargs)
        command_data = kwargs['command_data']
        to_addr = command_data['to_addr']
        content = command_data['content']
        msg_options = command_data['msg_options']
        in_reply_to = msg_options.pop('in_reply_to', None)
        if in_reply_to:
            msg = yield self.vumi_api.mdb.get_inbound_message(in_reply_to)
            if msg:
                # We can't override transport_name in reply_to(), so we set it
                # on the message we're replying to.
                msg['transport_name'] = msg_options['transport_name']
                yield self.reply_to(msg, content)
            else:
                log.warning('Unable to reply, message %s does not exist.' % (
                    in_reply_to))
        else:
            yield self.send_to(
                to_addr, content, endpoint='default', **msg_options)
