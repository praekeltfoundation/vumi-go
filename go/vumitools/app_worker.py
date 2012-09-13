from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.application import ApplicationWorker

from go.vumitools.api import VumiApiCommand, VumiApi, VumiUserApi, VumiApiEvent
from go.vumitools.api_worker import GoMessageMetadata


class GoApplicationMixin(object):

    def _go_validate_config(self):
        self.worker_name = self.config.get('worker_name', self.worker_name)
        self.api_routing_config = VumiApiCommand.default_routing_config()
        self.api_routing_config.update(self.config.get('api_routing', {}))
        self.app_event_routing_config = VumiApiEvent.default_routing_config()
        self.app_event_routing_config.update(
            self.config.get('app_event_routing', {}))
        self.control_consumer = None

    @inlineCallbacks
    def _go_setup_application(self):
        self.vumi_api = yield VumiApi.from_config_async(self.config)

        # In case we need these.
        self.redis = self.vumi_api.redis
        self.manager = self.vumi_api.manager

        self.app_event_publisher = yield self.publish_to(
            self.app_event_routing_config['routing_key'])

        self.control_consumer = yield self.consume(
            '%s.control' % (self.worker_name,),
            self.consume_control_command,
            exchange_name=self.api_routing_config['exchange'],
            exchange_type=self.api_routing_config['exchange_type'],
            message_class=VumiApiCommand)

    @inlineCallbacks
    def _go_teardown_application(self):
        # Sometimes something else closes our Redis connection.
        if self.redis is not None:
            yield self.redis.close_manager()
        if self.control_consumer is not None:
            yield self.control_consumer.stop()
            self.control_consumer = None

    def get_user_api(self, user_account_key):
        return VumiUserApi(self.vumi_api, user_account_key)

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
            return self.process_unknown_cmd(cmd_method_name, )

    def process_unknown_cmd(self, method_name, *args, **kwargs):
        log.error("Unknown vumi API command: %s(%s, %s)" % (
            method_name, args, kwargs))

    @inlineCallbacks
    def get_contact_for_message(self, message):
        helper_metadata = message.get('helper_metadata', {})

        go_metadata = helper_metadata.get('go', {})
        account_key = go_metadata.get('user_account', None)
        conversation_key = go_metadata.get('conversation_key', None)

        if account_key and conversation_key:
            user_api = self.get_user_api(account_key)
            conv = yield user_api.get_wrapped_conversation(conversation_key)
            contact = yield user_api.contact_store.contact_for_addr(
                conv.delivery_class, message.user())

            returnValue(contact)

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

    def get_go_metadata(self, msg):
        return GoMessageMetadata(self.vumi_api, msg)

    @inlineCallbacks
    def event_for_message(self, message, event_type, content):
        gmt = self.get_go_metadata(message)
        account_key = yield gmt.get_account_key()
        conversation_key, conversation_type = yield gmt.get_conversation_info()
        event = VumiApiEvent.event(account_key, conversation_key,
                                    event_type, content)
        returnValue(event)

    @inlineCallbacks
    def trigger_event(self, message, event_type, content):
        event = yield self.event_for_message(message, event_type, content)
        yield self.publish_app_event(event)

    def publish_app_event(self, event):
        self.app_event_publisher.publish_message(event)


class GoApplicationWorker(GoApplicationMixin, ApplicationWorker):
    """
    A base class for Vumi Go application worker.

    Configuration parameters:

    :type worker_name: str
    :param worker_name:
        The name of this worker, used for receiving control messages.

    """

    worker_name = None

    def validate_config(self):
        return self._go_validate_config()

    def setup_application(self):
        return self._go_setup_application()

    def teardown_application(self):
        return self._go_teardown_application()
