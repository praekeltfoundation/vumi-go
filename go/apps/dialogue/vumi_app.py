# -*- test-case-name: go.apps.dialogue.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
import pkg_resources

from vumi import log
from vumi.message import TransportUserMessage

from go.apps.jsbox.vumi_app import JsBoxConfig, JsBoxApplication


class DialogueConfig(JsBoxConfig):

    _cached_javascript = None

    @property
    def javascript(self):
        if self._cached_javascript is None:
            self._cached_javascript = pkg_resources.resource_string(
                "go.apps.dialogue", "vumi_app.js")
        return self._cached_javascript


class DialogueApplication(JsBoxApplication):
    CONFIG_CLASS = DialogueConfig

    worker_name = 'dialogue_application'

    def send_first_dialogue_message(self, to_addr, contact, conversation,
                                    msg_options):
        log.debug('Starting %r -> %s' % (conversation, to_addr))

        # We reverse the to_addr & from_addr since we're faking input
        # from the client to start the survey.
        from_addr = msg_options.pop('from_addr')
        conversation.set_go_helper_metadata(
            msg_options.setdefault('helper_metadata', {}))
        # TODO: This generates a fake message id that is then used in
        #       the reply to field of the outbound message. We need to
        #       write special version of the GoOutboundResource that
        #       will set in_reply_to to None on these messages so the
        #       invalid ids don't escape into the rest of the system.
        msg = TransportUserMessage(from_addr=to_addr, to_addr=from_addr,
                                   content=None, **msg_options)
        return self.consume_user_message(msg)

    @inlineCallbacks
    def process_command_send_dialogue(self, user_account_key, conversation_key,
                                      batch_id, msg_options,
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
                yield self.send_first_dialogue_message(
                    to_addr, contact, conv, msg_options)
