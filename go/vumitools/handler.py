# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi event handlers for use with EventDispatcher in vumitools api_worker"""

from twisted.internet.defer import inlineCallbacks

from vumi import log

from go.vumitools.api import VumiApiCommand


class EventHandler(object):
    def __init__(self, dispatcher, config):
        self.dispatcher = dispatcher
        self.config = config

    def get_user_api(self, account_key):
        return self.dispatcher.vumi_api.get_user_api(account_key)

    def setup_handler(self):
        pass

    def teardown_handler(self):
        pass

    def handle_event(self, event, handler_config):
        raise NotImplementedError()


class LoggingHandler(EventHandler):

    def handle_event(self, event, handler_config):
        log.info("LoggingHandler handling event: %s with config: %s" % (
            event, handler_config))


class SendMessageCommandHandler(EventHandler):

    @inlineCallbacks
    def handle_event(self, event, handler_config):
        """
        From an account and conversation, this finds a batch and a tag.
        While there could be multiple batches per conversation and
        multiple tags per batch, this assumes lists of one, and takes
        the first entry of each list

        TODO: Turn this into a generic API Command Sender?

        An Example of a event_dispatcher.yaml config file, with mapped
        conversations in the config:

            transport_name: event_dispatcher
            event_handlers:
                sign_up_handler: go.vumitools.handler.SendMessageCommandHandler
            account_handler_configs:
                '73ad76ec8c2e40858dc9d6b934049d95':
                - - ['a6a20571e77f4aa89a8b10a771b005bc', sign_up]
                  - - [ sign_up_handler, {
                      worker_name: 'multi_survey_application',
                      conversation_key: 'a6a20571e77f4aa89a8b10a771b005bc'
                      }
                  ]
        """

        log.info(
            "SendMessageCommandHandler handling event: %s with config: %s" % (
                event, handler_config))

        user_api = self.get_user_api(event.payload['account_key'])
        conv = yield user_api.conversation_store.get_conversation_by_key(
            event.payload['conversation_key'])
        conv = user_api.wrap_conversation(conv)

        command_data = event.payload['content']
        command_data['batch_id'] = conv.batch.key
        command_data['msg_options'] = {
            'helper_metadata': {
                'go': {'user_account': event.payload['account_key']},
            },
        }

        sm_cmd = VumiApiCommand.command(
            handler_config['worker_name'],
            "send_message",
            command_data=command_data,
            conversation_key=handler_config['conversation_key'],
            account_key=event.payload['account_key'])
        log.info("Publishing command: %s" % sm_cmd)
        self.dispatcher.api_command_publisher.publish_message(sm_cmd)
