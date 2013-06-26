# -*- test-case-name: go.vumitools.tests.test_routing -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.dispatchers.endpoint_dispatchers import RoutingTableDispatcher
from vumi.config import ConfigDict, ConfigText
from vumi.message import TransportEvent
from vumi import log

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin
from go.vumitools.account import GoConnector


class RoutingError(Exception):
    """Raised when an error occurs during routing."""


class UnroutableMessageError(RoutingError):
    """Raised when a message is unroutable."""
    def __init__(self, reason, msg):
        super(RoutingError, self).__init__(reason, msg)


class InvalidConnectorError(RoutingError):
    """Raised when an invalid connector name is encountered."""


class RoutingMetadata(object):
    """Helps manage Vumi Go routing metadata on a message.

    Adds support for `go_hops` and `go_outbound_hops`.

    The hops are both lists of `[source, destination]`. A `source` is
    a pair of a `GoConnector` string and an endpoint name and
    represents connector and endpoint the `AccountRoutingTableDispatcher`
    received the message on. The `destination` represents the connector
    and endpoint the message was published on after being received.

    The `go_outbound_hops` is a cache of the `go_hops` for the outbound
    message associated with an event. `go_outbound_hops` is only written
    to event messages. It allows dispatching events through multiple
    routing blocks while only retrieving the outbound message from the
    message store once.
    """

    def __init__(self, msg, outbound=None):
        self._msg = msg

    def get_hops(self):
        """Return a reference to the hops list for the message."""
        hops = self._msg['routing_metadata'].setdefault('go_hops', [])
        return hops

    def get_outbound_hops(self):
        """Return a reference to the cached outbound hops list.

        Returns None if no cached outbound hops are present.
        """
        outbound_hops = self._msg['routing_metadata'].get('go_outbound_hops')
        return outbound_hops

    def set_outbound_hops(self, outbound_hops):
        """Set the cached list of outbound hops."""
        self._msg['routing_metadata']['go_outbound_hops'] = outbound_hops[:]

    def push_hop(self, source, destination):
        """Appends a `[source, destination]` pair to the hops list."""
        hops = self.get_hops()
        hops.append([source, destination])

    def push_source(self, go_connector_str, endpoint):
        """Append a new hop to the hops list with destination set to None.

        Checks that the previous hop (if any) does not have a None
        destination.
        """
        source = [go_connector_str, endpoint]
        hops = self.get_hops()
        if hops and hops[-1][1] is None:
            raise RoutingError(
                "Attempt to push source hop twice in a row. First source was"
                " %r. Second source was %r." % (hops[-1][1], source),
                self._msg)
        hops.append([source, None])

    def push_destination(self, go_connector_str, endpoint):
        """Set the destination of the most recent hop.

        Checks that the most recent hop has an endpoint of None.
        """
        destination = [go_connector_str, endpoint]
        hops = self.get_hops()
        if not hops or hops[-1][1] is not None:
            raise RoutingError(
                "Attempt to push destination hop without first pushing the"
                " source hop. Destination is %r" % (destination,), self._msg)
        hops[-1][1] = destination

    def next_hop(self):
        """Computes the next hop assuming this message is following the
        inverse of the hops contained in the cached outbound hops list.

        Assumes the cached outbound hops list has been set and that
        `push_source` has been called with the most recent source hop.

        Returns the appropriate destination hop or `None` if no
        appropriate hop can be determined.
        """
        hops = self.get_hops()
        outbound_hops = self.get_outbound_hops()
        if not hops or not outbound_hops or len(hops) > len(outbound_hops):
            return None
        if hops[-1][1] is not None:  # check source hop was set
            return None
        # Note: outbound source is the event destination (and vice versa).
        [outbound_src, outbound_dst] = outbound_hops[-len(hops)]
        if outbound_dst != hops[-1][0]:
            return None
        return outbound_src


class AccountRoutingTableDispatcherConfig(RoutingTableDispatcher.CONFIG_CLASS,
                                          GoWorkerConfigMixin):
    application_connector_mapping = ConfigDict(
        "Mapping from conversation_type to connector name.",
        static=True, required=True)
    router_inbound_connector_mapping = ConfigDict(
        "Mapping from router_type to connector name to publish inbound"
        " messages on.",
        static=True, required=True)
    router_outbound_connector_mapping = ConfigDict(
        "Mapping from router_type to connector name to publish outbound"
        " messages on.",
        static=True, required=True)
    opt_out_connector = ConfigText(
        "Connector to publish opt-out messages on.",
        static=True, required=True)
    user_account_key = ConfigText(
        "Key of the user account the message is from.")


class AccountRoutingTableDispatcher(RoutingTableDispatcher, GoWorkerMixin):
    """
    Provides routing dispatching for Vumi Go accounts.

    Broadly, the strategy is to determine a user account key for the message
    and look up its associated routing table. The user account key is
    determined either based on the tag (if the message is inbound from
    a transport) or retrieved from the Vumi Go metadata.

    Events ignore the routing table and follow the reverse of the route
    that the associated outbound message was sent out via.

    Messages from transports that look like opt-out messages are routed
    straight to the opt-out worker and replies from the opt-out worker
    go straight back to the transport the original message came from.

    Summary of message sources and destinations:

    * inbound messages:
      * from: transports or routing blocks
      * to: routing blocks, conversations or the opt-out worker

    * outbound messages:
      * from: conversations, routing blocks or the opt-out worker
      * to: routing blocks or transports

    * events:
      * from: transports or routing blocks
      * to: routing blocks, conversations or the opt-out worker

    Further complexities arise because routing blocks can be sources
    and destinations of both inbound and outbound messages (and events)
    so care has to be taken to keep track of which direction a message
    is travelling in in order to select the correct routing table
    entry when routing messages from dispatchers.

    Summary of how user account keys are determined:

    * for messages from transports:
      * tag is used to determine the user account id

    * for routing blocks, conversations and the opt-out worker:
      * the user account id is read from the Vumi Go helper_metadata.

    When messages are published the following helper_metadata
    is included:

    * for transports: tag pool and tag name
    * for routing blocks: user_account, router_type, router_key
    * for conversations: user_account, conversation_type, conversation_key
    * for the opt-out worker: user_account

    Messages received from these sources are expected to include the same
    metadata.
    """

    CONFIG_CLASS = AccountRoutingTableDispatcherConfig
    worker_name = 'account_routing_table_dispatcher'

    # connector types (references to GoConnector constants for convenience)
    CONVERSATION = GoConnector.CONVERSATION
    ROUTING_BLOCK = GoConnector.ROUTING_BLOCK
    TRANSPORT_TAG = GoConnector.TRANSPORT_TAG
    OPT_OUT = GoConnector.OPT_OUT

    # directions (references to GoConnector constants for convenience)
    INBOUND = GoConnector.INBOUND
    OUTBOUND = GoConnector.OUTBOUND

    @inlineCallbacks
    def setup_dispatcher(self):
        yield super(AccountRoutingTableDispatcher, self).setup_dispatcher()
        yield self._go_setup_worker()
        config = self.get_static_config()
        self.opt_out_connector = config.opt_out_connector
        self.router_inbound_connector_mapping = (
            config.router_inbound_connector_mapping)
        self.router_outbound_connecor_mapping = (
            config.router_outbound_connector_mapping)
        self.router_connectors = set()
        self.router_connectors.update(
            config.router_inbound_connector_mapping.itervalues())
        self.router_connectors.update(
            config.router_outbound_connector_mapping.itervalues())
        self.application_connector_mapping = (
            config.application_connector_mapping)
        self.application_connectors = set(
            config.application_connector_mapping.itervalues())
        self.transport_connectors = set()
        self.transport_connectors.update(
            config.receive_inbound_connectors)
        self.transport_connectors.discard(
            self.router_connectors)

    @inlineCallbacks
    def teardown_dispatcher(self):
        yield self._go_teardown_worker()
        yield super(AccountRoutingTableDispatcher, self).teardown_dispatcher()

    @inlineCallbacks
    def get_config(self, msg):
        """Determine the config (primarily the routing table) for the given
        event or transport user message.

        If the message is an event, we skip looking up the account since
        events largely ignore the routing table.

        For a given message there are two cases. Either it already has
        a user account key in the Vumi Go helper metadata, or it is from
        a transport and has a tag.
        """
        if isinstance(msg, TransportEvent):
            config_dict = self.config.copy()
            config_dict['user_account_key'] = None
            config_dict['routing_table'] = {}
            returnValue(self.CONFIG_CLASS(config_dict))

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
        elif connector_name in self.router_connectors:
            return self.ROUTING_BLOCK
        elif connector_name in self.transport_connectors:
            return self.TRANSPORT_TAG
        elif connector_name == self.opt_out_connector:
            return self.OPT_OUT
        else:
            raise InvalidConnectorError(
                "Connector %r is not a valid connector name"
                % (connector_name,))

    def get_application_connector(self, conversation_type):
        return self.application_connector_mapping.get(conversation_type)

    def get_router_connector(self, router_type, direction):
        if direction == self.INBOUND:
            return self.router_inbound_connector_mapping.get(router_type)
        else:
            return self.router_outbound_connecor_mapping.get(router_type)

    def router_direction(self, direction):
        """Converts an connector direction (as seen from the perspective of
        this app) into the direction as seen by a routing block (i.e. the
        reverse).
        """
        router_direction = {
            self.INBOUND: self.OUTBOUND,
            self.OUTBOUND: self.INBOUND,
        }.get(direction)
        return router_direction

    @inlineCallbacks
    def set_destination(self, msg, target, direction):
        """Parse a target `(str(go_connector), endpoint)` pair and determine
        the corresponding dispatcher connector to publish on. Set any
        appropriate Go helper_metadata required by the destination.

        Raises `UnroutableMessageError` if the parsed `GoConnector` has a
        connector type not approriate to the message direction.

        Note: `str(go_connector)` is what is stored in Go routing tables.
        """
        msg_mdh = self.get_metadata_helper(msg)
        conn = GoConnector.parse(target[0])

        if direction == self.INBOUND:
            allowed_types = (
                self.CONVERSATION, self.ROUTING_BLOCK, self.OPT_OUT)
        else:
            allowed_types = (
                self.ROUTING_BLOCK, self.TRANSPORT_TAG)

        if conn.ctype not in allowed_types:
            raise UnroutableMessageError(
                "Destination connector of invalid type: %s" % conn, msg)

        if conn.ctype == conn.CONVERSATION:
            msg_mdh.set_conversation_info(conn.conv_type, conn.conv_key)
            dst_connector_name = self.get_application_connector(conn.conv_type)

        elif conn.ctype == conn.ROUTING_BLOCK:
            msg_mdh.set_router_info(conn.rblock_type, conn.rblock_key)
            dst_connector_name = self.get_router_connector(
                conn.rblock_type, self.router_direction(direction))

        elif conn.ctype == conn.TRANSPORT_TAG:
            msg_mdh.set_tag([conn.tagpool, conn.tagname])
            tagpool_metadata = yield self.vumi_api.tpm.get_metadata(
                conn.tagpool)
            transport_name = tagpool_metadata.get('transport_name')
            if transport_name is None:
                raise UnroutableMessageError(
                    "No transport name found for tagpool %r"
                    % conn.tagpool, msg)
            if self.connector_type(transport_name) != self.TRANSPORT_TAG:
                raise UnroutableMessageError(
                    "Transport name %r found in tagpool metadata for pool"
                    " %r is invalid." % (transport_name, conn.tagpool), msg)
            dst_connector_name = transport_name

        elif conn.ctype == conn.OPT_OUT:
            dst_connector_name = self.opt_out_connector

        else:
            raise UnroutableMessageError(
                "Serious error. Reached apparently unreachable state"
                " in which destination connector type is valid but"
                " unknown. Bad connector is: %s" % conn, msg)

        rmeta = RoutingMetadata(msg)
        rmeta.push_destination(str(conn), target[1])
        returnValue((dst_connector_name, target[1]))

    def acquire_source(self, msg, connector_type, direction):
        """Determine the `str(go_connector)` value that a msg came
        in on by looking at the connector_type and fetching the
        appropriate values from the `msg` helper_metadata.

        Raises `UnroutableMessageError` if the connector_type has a
        value not appropriate for the direction.

        Note: `str(go_connector)` is what is stored in Go routing tables.
        """
        msg_mdh = self.get_metadata_helper(msg)

        if direction == self.INBOUND:
            allowed_types = (self.TRANSPORT_TAG, self.ROUTING_BLOCK)
        else:
            allowed_types = (self.CONVERSATION, self.ROUTING_BLOCK,
                             self.OPT_OUT)

        if connector_type not in allowed_types:
            raise UnroutableMessageError(
                "Source connector of invalid type: %s" % connector_type, msg)

        if connector_type == self.CONVERSATION:
            conv_info = msg_mdh.get_conversation_info()
            src_conn = str(GoConnector.for_conversation(
                conv_info['conversation_type'], conv_info['conversation_key']))

        elif connector_type == self.ROUTING_BLOCK:
            router_info = msg_mdh.get_router_info()
            src_conn = str(GoConnector.for_routing_block(
                router_info['router_type'], router_info['router_key'],
                self.router_direction(direction)))

        elif connector_type == self.TRANSPORT_TAG:
            src_conn = str(GoConnector.for_transport_tag(*msg_mdh.tag))

        elif connector_type == self.OPT_OUT:
            src_conn = str(GoConnector.for_opt_out())

        else:
            raise UnroutableMessageError(
                "Serious error. Reached apparently unreachable state"
                " in which source connector type is both valid"
                " but unknown. Bad connector type is: %s"
                % connector_type, msg)

        src_conn_str = str(src_conn)
        rmeta = RoutingMetadata(msg)
        rmeta.push_source(src_conn_str, msg.get_routing_endpoint())
        return src_conn_str

    @inlineCallbacks
    def publish_inbound_optout(self, config, msg):
        """Publish an inbound opt-out request to the opt-out worker."""
        target = [str(GoConnector.for_opt_out()), 'default']
        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, target, self.INBOUND)
        yield self.publish_inbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
    def publish_outbound_optout(self, config, msg):
        """Publish a reply from the opt-out worker.

        It does this by looking up the original message and
        sending the reply out via the same tag the original
        message came in on.
        """
        orig_msg = yield self.find_message_for_reply(msg)
        if orig_msg is None:
            raise UnroutableMessageError(
                "Could not find original message for reply from"
                " the opt-out worker", msg)
        orig_msg_mdh = self.get_metadata_helper(orig_msg)
        if orig_msg_mdh.tag is None:
            raise UnroutableMessageError(
                "Could not find tag on original message for reply"
                " from the opt-out worker", msg)
        dst_conn = GoConnector.for_transport_tag(*orig_msg_mdh.tag)
        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, [str(dst_conn), 'default'], self.OUTBOUND)
        yield self.publish_outbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
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
        src_conn = self.acquire_source(msg, connector_type, self.INBOUND)

        if (connector_type == self.TRANSPORT_TAG
                and msg_mdh.is_optout_message()):
            yield self.publish_inbound_optout(config, msg)
            return

        target = self.find_target(config, msg, src_conn)
        if target is None:
            log.debug("No target found for message from '%s': %s" % (
                connector_name, msg))
            return

        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, target, self.INBOUND)

        yield self.publish_inbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
    def process_outbound(self, config, msg, connector_name):
        """Process an outbound message.

        Outbound messages can be from:

        * conversations
        * routing blocks
        * the opt-out worker

        And may go to:

        * routing blocks
        * transports
        """
        log.debug("Processing outbound: %s" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        msg_mdh.set_user_account(config.user_account_key)

        connector_type = self.connector_type(connector_name)
        src_conn = self.acquire_source(msg, connector_type, self.OUTBOUND)

        if connector_type == self.OPT_OUT:
            yield self.publish_outbound_optout(config, msg)
            return

        target = self.find_target(config, msg, src_conn)
        if target is None:
            log.debug("No target found for message from '%s': %s" % (
                connector_name, msg))
            return

        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, target, self.OUTBOUND)

        yield self.publish_outbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
    def _set_event_metadata(self, event):
        """Sets the user account, tag and outbound hops metadata on an event
        if it does not already have them.
        """
        # TODO: the setdefault can be removed once Vumi events have
        #       helper_metadata
        event.payload.setdefault('helper_metadata', {})
        event_mdh = self.get_metadata_helper(event)
        event_rmeta = RoutingMetadata(event)

        if (event_rmeta.get_outbound_hops() is not None
            and event_mdh.has_user_account()
            and event_mdh.tag is not None):
                return

        # some metadata is missing, grab the associated outbound message
        # and look for it there:

        msg = yield self.find_message_for_event(event)
        if msg is None:
            raise UnroutableMessageError(
                "Could not find transport user message for event", event)
        msg_mdh = self.get_metadata_helper(msg)
        if not msg_mdh.has_user_account():
            raise UnroutableMessageError(
                "Outbound message for event has no associated"
                " user account: %r" % (msg,), event)
        if msg_mdh.tag is None:
            raise UnroutableMessageError(
                "Outbound message for event has no tag set: %r" % (msg,),
                event)

        # set the tag on the event so that if it is from a transport
        # we can set the source of the message correctly in acquire_source.
        event_mdh.set_tag(msg_mdh.tag)
        event_mdh.set_user_account(msg_mdh.get_account_key())
        msg_rmeta = RoutingMetadata(msg)
        event_rmeta.set_outbound_hops(msg_rmeta.get_hops())

    @inlineCallbacks
    def process_event(self, config, event, connector_name):
        """Process an event message.

        Events must trace back the path through the routing blocks
        and conversations that was taken by the associated outbound
        message.

        Events thus ignore the routing table itself.

        Events can be from:

        * transports
        * routing blocks

        And may go to:

        * routing blocks
        * conversations
        * the opt-out worker
        """
        log.debug("Processing event: %s" % (event,))

        # events are in same direction as inbound messages so
        # we use INBOUND as the direction in this method.

        yield self._set_event_metadata(event)

        connector_type = self.connector_type(connector_name)
        # we ignore the source connector returned but .acquire_source() sets
        # the initial hop and .next_hop() checks that it matches the outbound
        # destination.
        self.acquire_source(event, connector_type, self.INBOUND)

        rmeta = RoutingMetadata(event)
        target = rmeta.next_hop()
        if target is None:
            raise UnroutableMessageError(
                "Could not find next hop for event.", event)

        dst_connector_name, dst_endpoint = yield self.set_destination(
            event, target, self.INBOUND)
        yield self.publish_event(event, dst_connector_name, dst_endpoint)
