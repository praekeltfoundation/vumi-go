# -*- test-case-name: go.vumitools.tests.test_routing -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.dispatchers.endpoint_dispatchers import RoutingTableDispatcher
from vumi.config import ConfigDict, ConfigText
from vumi.message import TransportEvent
from vumi import log

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin
from go.vumitools.middleware import OptOutMiddleware
from go.vumitools.account import GoConnector


class RoutingError(Exception):
    """Raised when an error occurs during routing."""


class UnroutableMessageError(RoutingError):
    """Raised when a message is unroutable."""
    def __init__(self, reason, msg):
        super(RoutingError, self).__init__(reason, msg)


class AccountRoutingTableDispatcherConfig(RoutingTableDispatcher.CONFIG_CLASS,
                                          GoWorkerConfigMixin):
    application_connector_mapping = ConfigDict(
        "Mapping from conversation_type to connector name.",
        static=True, required=True)
    router_connector_mapping = ConfigDict(
        "Mapping from routing block type to connector name.",
        static=True, required=True)
    opt_out_connector = ConfigText(
        "Connector to publish opt-out messages on.",
        static=True, required=True)
    user_account_key = ConfigText(
        "Key of the user account the message is from.",
        required=True)


class AccountRoutingTableDispatcher(RoutingTableDispatcher, GoWorkerMixin):
    """

    inbound:
      * from transport:
      * from routing block:
      * to routing block
      * to conversation
      * to opt out

    outbound:
      * from conversation:
      * from routing block:
      * from opt out:
      * to routing block
      * to transport

    event:
      * trace back path of outbound message
      * from transport:
      * from routing blwock:
      * to routing block
      * to conversation
      * to opt out

    from transport:
      * tag used to determine account id

    from routing block:
      * account info in message

    from conversation:
      * account info in message

    from opt out:
      * account info in message

    also stores messages in the appropriate batch
    for conversations and routing blocks
    (storage middleware does this at the transport
     for transports)

    TODO: decide what happens at transports to tags
    without an associated batch / account
    (I guess we should log an error and put them in
     a generic batch bucket for later analysis).
    """

    CONFIG_CLASS = AccountRoutingTableDispatcherConfig
    worker_name = 'account_routing_table_dispatcher'

    # connector types
    CONVERSATION = "CONVERSATION"
    ROUTING_BLOCK = "ROUTING_BLOCK"
    TRANSPORT = "TRANSPORT"
    OPT_OUT = "OPT_OUT"

    @inlineCallbacks
    def setup_dispatcher(self):
        yield super(AccountRoutingTableDispatcher, self).setup_dispatcher()
        yield self._go_setup_worker()
        config = self.get_static_config()
        self.router_connector_mapping = config.router_connector_mapping
        self.router_connectors = set(
            config.router_connector_mapping.itervalues())
        self.application_connector_mapping = (
            config.application_connector_mapping)
        self.application_connectors = set(
            config.application_connector_mapping.itervalues())

    @inlineCallbacks
    def teardown_dispatcher(self):
        yield super(AccountRoutingTableDispatcher, self).teardown_dispatcher()
        yield self._go_teardown_worker()

    @inlineCallbacks
    def get_config(self, msg):
        """Determine the config (primarily the routing table) for the given
        event or transport user message.

        If the message is an event, we first look up the original message.

        For a given message there are two cases. Either it already has
        a user account key in the Vumi Go helper metadata, or it is from
        a transport and has a tag.
        """
        if isinstance(msg, TransportEvent):
            event = msg
            msg = yield self.find_message_for_event(event)
            if msg is None:
                raise UnroutableMessageError(
                    "Could not find transport user message for event", event)

        msg_mdh = self.get_metadata_helper(msg)

        if msg_mdh.has_user_account():
            user_account_key = msg_mdh.get_account_key()
        elif msg_mdh.tag is not None:
            tag_info = yield self.vumi_api.mdb.get_tag_info(tuple(msg_mdh.tag))
            user_account_key = tag_info.metadata['user_account']
        else:
            raise UnroutableMessageError(
                "Could not determine user account key", msg)

        user_api = self.get_user_api(user_account_key)
        routing_table = yield user_api.get_routing_table()

        config_dict = self.config.copy()
        config_dict['user_account_key'] = user_account_key
        config_dict['routing_table'] = routing_table

        returnValue(self.CONFIG_CLASS(config_dict))

    def connector_type(self, connector_name):
        if connector_name in self.application_connectors:
            return self.CONVERSATION
        elif connector_name in self.routing_connectors:
            return self.ROUTING_BLOCK
        elif connector_name == self.opt_out_connector:
            return self.OPT_OUT
        return self.TRANSPORT

    def get_application_connector(self, conversation_type):
        return self.application_connector_mapping.get(conversation_type)

    def get_router_connector(self, router_type):
        return self.router_connector_mapping.get(router_type)

    def process_inbound(self, config, msg, connector_name):
        """Process an inbound message.

        Inbound messages can be from:

        * transports (these might be opt-out messages)
        * routing blocks

        And may go to:

        * routing blocks
        * conversations
        * the opt-out worker
        """
        log.debug("Processing inbound: %r" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        msg_mdh.set_user_account(config.user_account_key)

        connector_type = self.connector_type(connector_name)

        if connector_type == self.TRANSPORT and msg_mdh.is_optout_message():
            return self.publish_inbound(
                msg, config.opt_out_connector, 'default')

        if connector_type == self.TRANSPORT:
            src_conn = str(GoConnector.for_transport_tag(*msg_mdh.tag))
        elif connector_type == self.ROUTER:
            src_conn = str(GoConnector.for_routing_block())
        else:
            raise UnroutableMessageError(
                "Inbound message from a source other than a transport"
                "or routing block. Source was: %r" % connector_name, msg)

        target = self.find_target(config, msg, src_conn)
        if target is None:
            log.debug("No target found for message from '%s': %s" % (
                connector_name, msg))
            return

        dst_conn = GoConnector.parse(target[0])
        if dst_conn.ctype == dst_conn.CONVERSATION:
            msg_mdh.set_conversation_info(
                dst_conn.conv_type, dst_conn.conv_key)
            dst_connector_name = self.get_application_connector(
                dst_conn.conv_type)
        elif dst_conn.ctype == dst_conn.ROUTING_BLOCK:
            msg_mdh.set_router_info(
                dst_conn.rblock_type, dst_conn.rblock_key)
            dst_connector_name = self.get_router_connector(
                dst_conn.rblock_type)
        else:
                raise UnroutableMessageError(
                "Inbound message being routed towards invalid target."
                " Source was: %r. Target was: %r."
                % (connector_name, target[0]), msg)

        return self.publish_inbound(msg, dst_connector_name, target[1])

    def process_outbound(self, config, msg, connector_name):
        log.debug("Processing outbound: %s" % (msg,))
        if not config.conversation_info:
            log.warning(
                "No conversation info found for outbound message: %s" % (msg,))
            return

        if OptOutMiddleware.is_optout_message(msg):
            return self.handle_outbound_opt_out(msg)

        conv_conn = str(GoConnector.for_conversation(
            config.conversation_info['conversation_type'],
            config.conversation_info['conversation_key']))
        target = self.find_target(config, msg, conv_conn)
        if target is None:
            log.debug("No target found for message from '%s': %s" % (
                connector_name, msg))
            return

        conn = GoConnector.parse(target[0])
        assert conn.ctype == conn.TRANSPORT_TAG
        tag = [conn.tagpool, conn.tagname]
        msg['helper_metadata'].setdefault('tag', {})['tag'] = tag

        def publish_cb(tagpool_metadata):
            transport_name = tagpool_metadata.get('transport_name')
            if transport_name is None:
                log.warning("No transport_name for tag: %r" % (tag,))
                return

            return self.publish_outbound(msg, transport_name, target[1])

        d = self.vumi_api.tpm.get_metadata(tag[0])
        d.addCallback(publish_cb)
        return d

    def process_event(self, config, event, connector_name):
        log.debug("Processing event: %s" % (event,))
        if not config.conversation_info:
            log.warning("No conversation info found on outbound message "
                        "for event: %s" % (event,))
            return
        conv_type = config.conversation_info['conversation_type']
        conv_connector = self.get_application_connector(conv_type)
        return self.publish_event(event, conv_connector, "default")
