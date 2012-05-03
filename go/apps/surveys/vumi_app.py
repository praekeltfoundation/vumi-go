from twisted.internet.defer import inlineCallbacks
from go.vumitools.api import VumiApiCommand, get_redis
from vxpolls.example import PollApplication
from vumi.persist.message_store import MessageStore
from vumi.persist.txriak_manager import TxRiakManager
from vumi.message import TransportUserMessage
from vumi import log


class SurveyApplication(PollApplication):

    def validate_config(self):
        super(SurveyApplication, self).validate_config()

        self.worker_name = self.config.get('worker_name')
        # message store
        mdb_config = self.config.get('message_store', {})
        self.mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        # api worker
        self.api_routing_config = VumiApiCommand.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        self.control_consumer = None

    @inlineCallbacks
    def setup_application(self):
        yield super(SurveyApplication, self).setup_application()
        r_server = get_redis(self.config)
        self.manager = TxRiakManager.from_config({
                'bucket_prefix': self.mdb_prefix})
        self.store = MessageStore(self.manager, r_server, self.mdb_prefix)
        self.control_consumer = yield self.consume(
            '%s.control' % (self.worker_name,),
            self.consume_control_command,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiCommand)

    @inlineCallbacks
    def teardown_application(self):
        yield super(SurveyApplication, self).teardown_application()
        if self.control_consumer is not None:
            yield self.control_consumer.stop()
            self.control_consumer = None

    def consume_user_message(self, message):
        helper_metadata = message['helper_metadata']
        conv_info = helper_metadata.get('conversations')
        helper_metadata['poll_id'] = 'poll-%s' % (
                conv_info.get('conversation_id'),)
        super(SurveyApplication, self).consume_user_message(message)

    def consume_control_command(self, command_message):
        """
        Handle a VumiApiCommand message that has arrived.

        :type command_message: VumiApiCommand
        :param command_message:
            The command message received for this application.
        """
        cmd_method_name = 'process_command_%s' % (
            command_message.get('command'),)
        cmd_method = getattr(self, cmd_method_name,
                             self.process_unknown_cmd)
        return cmd_method(command_message)

    def process_unknown_cmd(self, command_message):
        log.error("Unknown vumi API command: %r" % (command_message,))

    def process_command_send(self, cmd):
        message_options = cmd.get('msg_options', {})
        conversation_id = message_options['conversation_id']
        conversation_type = message_options['conversation_type']
        msg = TransportUserMessage(from_addr=cmd['to_addr'],
                to_addr=cmd['msg_options']['from_addr'],
                content=cmd['content'],
                transport_name=message_options['transport_name'],
                transport_type=message_options['transport_type'],
                helper_metadata={
                    'conversations': {
                        'conversation_id': conversation_id,
                        'conversation_type': conversation_type,
                    }
                })
        self.consume_user_message(msg)
