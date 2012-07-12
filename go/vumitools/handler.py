# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi event handlers for use with EventDispatcher in vumitools api_worker"""

from twisted.internet.defer import inlineCallbacks

from vumi import log

from go.vumitools.api import VumiApiCommand, VumiUserApi
from go.vumitools.conversation import ConversationStore


class EventHandler(object):
    def __init__(self, dispatcher, config):
        self.dispatcher = dispatcher
        self.config = config

    def setup_handler(self):
        pass

    def handle_event(self, event, handler_config):
        raise NotImplementedError()


class LoggingHandler(EventHandler):

    def handle_event(self, event, handler_config):
        log.info("LoggingHandler handling event: %s with config: %s" % (
            event, handler_config))


class SendMessageCommandHandler(EventHandler):

    def get_user_api(self, account_key, api_conf):
        return VumiUserApi(account_key, api_conf)

    @inlineCallbacks
    def handle_event(self, event, handler_config):
        """
        From an account and conversation, this finds a batch and a tag.
        While there could be multiple batches per conversation and
        multiple tags per batch, this assumes lists of one, and takes
        the first entry of each list
        """
        """
        An Example of a event_dispatcher.yaml config file, with mapped
        conversations in the config:
            transport_name: event_dispatcher
            r_prefix: vumigo
            message_store:
                store_prefix: vumigo.
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
        conv_store = ConversationStore(self.dispatcher.manager,
                                        event.payload['account_key'])
        conv = yield conv_store.get_conversation_by_key(
                                        event.payload['conversation_key'])
        api_conf = {
            'tagpool_manager': {
                'tagpool_prefix': self.dispatcher.r_prefix,
            },
            'riak_manager': {
                'bucket_prefix': self.dispatcher.mdb_prefix
            },
        }
        user_api = self.get_user_api(event.payload['account_key'], api_conf)
        conv = user_api.wrap_conversation(conv)

        batch_keys = conv.batches.keys()
        if len(batch_keys) > 0:
            batch_id = batch_keys[0]
        else:
            log.info("No batches found")
            return

        batch_tags = yield user_api.api.batch_tags(batch_id)
        if len(batch_tags) > 0:
            tag = [batch_tags[0][0], batch_tags[0][1]]
        else:
            log.info("No batch tags found")
            return

        tag_pools = yield user_api.tagpools()
        tag_info = tag_pools._pools[tag[0]]

        command_data = event.payload['content']
        command_data['batch_id'] = batch_id
        command_data['msg_options'] = {
                'helper_metadata': {
                    'go': {'user_account': event.payload['account_key']},
                    'tag': {'tag': tag},
                    'transport_type': tag_info['transport_type'],
                },
                'transport_type': tag_info['transport_type'],
                'transport_name': tag_info['msg_options']['transport_name'],
                'from_addr': tag[1],
        }

        sm_cmd = VumiApiCommand.command(
                handler_config['worker_name'],
                "send_message",
                command_data=command_data,
                conversation_key=handler_config['conversation_key'],
                account_key=event.payload['account_key']
                )
        log.info("Publishing command: %s" % sm_cmd)
        self.dispatcher.api_command_publisher.publish_message(sm_cmd)
