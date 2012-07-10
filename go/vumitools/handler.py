
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

    @inlineCallbacks
    def handle_event(self, event, handler_config):
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
        user_api = VumiUserApi(event.payload['account_key'],
                                                    api_conf)
        conv = user_api.wrap_conversation(conv)

        batch_id = conv.batches.keys()[0]
        batch_tags = user_api.api.batch_tags(batch_id)
        tag = [batch_tags[0][0], batch_tags[0][1]]
        tag_info = user_api.tagpools()._pools[tag[0]]
        event.payload['content']['batch_id'] = batch_id
        event.payload['content']['msg_options'] = {
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
                send_message = event.payload['content'],
                conversation_key=handler_config['conversation_key'],
                account_key=event.payload['account_key']
                )
        log.info("Publishing command: %s" % sm_cmd)
        self.dispatcher.api_command_publisher.publish_message(sm_cmd)


