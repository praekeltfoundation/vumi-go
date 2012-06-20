# -*- test-case-name: go.apps.opt_out.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from go.vumitools.api import VumiApiCommand, get_redis
from go.vumitools.conversation import ConversationStore
from go.vumitools.contact import ContactStore
from go.vumitools.opt_out import OptOutStore
from vumi.application import ApplicationWorker
from vumi.persist.message_store import MessageStore
from vumi.persist.txriak_manager import TxRiakManager
from vumi import log


class OptOutApplication(ApplicationWorker):

    def validate_config(self):
        self.worker_name = self.config['worker_name']
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
        if self.control_consumer is not None:
            yield self.control_consumer.stop()
            self.control_consumer = None

    @inlineCallbacks
    def get_contact_for_message(self, message):
        helper_metadata = message.get('helper_metadata', {})

        go_metadata = helper_metadata.get('go', {})
        account_key = go_metadata.get('user_account', None)

        conversation_metadata = helper_metadata.get('conversations', {})
        conversation_key = conversation_metadata.get('conversation_key', None)

        if account_key and conversation_key:
            conv_store = ConversationStore(self.manager, account_key)
            conv = yield conv_store.get_conversation_by_key(conversation_key)

            contact_store = ContactStore(self.manager, account_key)
            contact = yield contact_store.contact_for_addr(conv.delivery_class,
                message.user())

            returnValue(contact)

    @inlineCallbacks
    def consume_user_message(self, message):

        helper_metadata = message.get('helper_metadata', {})
        go_metadata = helper_metadata.get('go', {})
        account_key = go_metadata.get('user_account', None)
        opt_out_store = OptOutStore(self.manager, account_key)
        from_addr = message.get("from_addr")
        # Note: for now we are hardcoding addr_type as 'msisdn'
        # as only msisdn's are opting out currently
        yield opt_out_store.new_opt_out("msisdn", from_addr, message)

        if message.get('transport_type') == 'http_api':
            self.reply_to(message,
                '{"msisdn":"%s",'
                '"opted_in": false}' % (from_addr,))
        else:
            self.reply_to(message, "You have opted out")

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
