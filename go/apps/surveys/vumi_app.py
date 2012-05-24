# -*- test-case-name: go.apps.surveys.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks
from go.vumitools.api import VumiApiCommand, get_redis
from go.vumitools.conversation import ConversationStore
from vxpolls.example import PollApplication
from vxpolls.manager import PollManager
from vumi.persist.message_store import MessageStore
from vumi.persist.txriak_manager import TxRiakManager
from vumi.message import TransportUserMessage
from vumi import log


class SurveyApplication(PollApplication):

    def validate_config(self):
        self.worker_name = self.config['worker_name']
        # vxpolls
        vxp_config = self.config.get('vxpolls', {})
        self.poll_prefix = vxp_config.get('prefix')
        # message store
        mdb_config = self.config.get('message_store', {})
        self.mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        # api worker
        self.api_routing_config = VumiApiCommand.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        self.control_consumer = None

    @inlineCallbacks
    def setup_application(self):
        r_server = get_redis(self.config)
        self.pm = PollManager(r_server, self.poll_prefix)
        self.manager = TxRiakManager.from_config(
            self.config.get('riak_manager'))
        self.store = MessageStore(self.manager, r_server, self.mdb_prefix)
        self.control_consumer = yield self.consume(
            '%s.control' % (self.worker_name,),
            self.consume_control_command,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiCommand)

    @inlineCallbacks
    def teardown_application(self):
        self.pm.stop()
        if self.control_consumer is not None:
            yield self.control_consumer.stop()
            self.control_consumer = None

    def consume_user_message(self, message):
        helper_metadata = message['helper_metadata']
        conv_info = helper_metadata.get('conversations')
        helper_metadata['poll_id'] = 'poll-%s' % (
            conv_info.get('conversation_key'),)
        super(SurveyApplication, self).consume_user_message(message)

    def consume_control_command(self, command_message):
        """
        Handle a VumiApiCommand message that has arrived.

        :type command_message: VumiApiCommand
        :param command_message:
            The command message received for this application.
        """
        cmd_method_name = 'process_command_%(command)s' % command_message
        args = command_message['args']
        kwargs = command_message['kwargs']
        cmd_method = getattr(self, cmd_method_name, None)
        if cmd_method:
            return cmd_method(*args, **kwargs)
        else:
            return self.process_unknown_cmd(cmd_method_name, *args, **kwargs)

    def process_unknown_cmd(self, method_name, *args, **kwargs):
        log.error("Unknown vumi API command: %s(%s, %s)" % (
            method_name, args, kwargs))

    def start_survey(self, to_addr, conversation, **msg_options):
        log.debug('Starting %r -> %s' % (conversation, to_addr))

        helper_metadata = msg_options.setdefault('helper_metadata', {})
        helper_metadata['conversations'] = {
            'conversation_key': conversation.key,
            'conversation_type': conversation.conversation_type,
        }

        # We reverse the to_addr & from_addr since we're faking input
        # from the client to start the survey.
        from_addr = msg_options.pop('from_addr')
        msg = TransportUserMessage(from_addr=to_addr, to_addr=from_addr,
                content='', **msg_options)
        self.consume_user_message(msg)

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
        conversation_key, msg_options, is_client_initiated, **extra_params):

        if is_client_initiated:
            log.debug('Conversation %r is client initiated, no need to notify '
                'the application worker' % (conversation_key,))
            return

        batch = yield self.store.get_batch(batch_id)
        if batch:
            account_key = batch.metadata["user_account"]
            if account_key is None:
                log.error("No account key in batch metadata: %r" % (
                    batch,))
                return

            conv_store = ConversationStore(self.manager, account_key)
            conv = yield conv_store.get_conversation_by_key(conversation_key)

            to_addresses = yield conv.get_contacts_addresses()
            for to_addr in to_addresses:
                yield self.start_survey(to_addr, conv, **msg_options)
        else:
            log.error('No batch found for %s' % (batch_id,))
