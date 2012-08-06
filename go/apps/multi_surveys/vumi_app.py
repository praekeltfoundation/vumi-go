# -*- test-case-name: go.apps.multi_surveys.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from vxpolls.multipoll_example import MultiPollApplication
from vxpolls.manager import PollManager

from vumi.message import TransportUserMessage
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin


def hacky_hack_hack(config):
    from vumi.persist.redis_manager import RedisManager
    hacked_config = config.copy()
    hacked_config['key_prefix'] = ""
    hacked_config['key_separator'] = ""
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

    worker_name = None

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

    def consume_user_message(self, message):
        helper_metadata = message['helper_metadata']
        go = helper_metadata.get('go')
        helper_metadata['poll_id'] = 'poll-%s' % (
            go.get('conversation_key'),)
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

        to_addresses = yield conv.get_opted_in_addresses()
        for to_addr in to_addresses:
            yield self.start_survey(to_addr, conv, **msg_options)
