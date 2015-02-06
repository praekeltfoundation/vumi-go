# -*- test-case-name: go.vumitools.tests.test_routing -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor

from vumi.dispatchers.endpoint_dispatchers import RoutingTableDispatcher
from vumi.config import ConfigDict, ConfigText, ConfigFloat, ConfigBool
from vumi.message import TransportEvent
from vumi import log

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin
from go.vumitools.model_object_cache import ModelObjectCache
from go.vumitools.routing_table import GoConnector
from go.vumitools.opt_out.utils import OptOutHelper


class RoutingError(Exception):
    """Raised when an error occurs during routing."""


class UnroutableMessageError(RoutingError):
    """Raised when a message is unroutable."""
    def __init__(self, reason, msg):
        super(RoutingError, self).__init__(reason, msg)


class InvalidConnectorError(RoutingError):
    """Raised when an invalid connector name is encountered."""


class UnownedTagError(RoutingError):
    """Raised when a message is received on an unowned tag."""


class NoTargetError(RoutingError):
    """
    Raised when a there is no entry for a source connector in an account
    routing table.
    """

REPLYABLE_ERRORS = (UnownedTagError, NoTargetError)


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
    routers while only retrieving the outbound message from the message
    store once.
    """

    def __init__(self, msg, outbound=None):
        self._msg = msg

    def get_hops(self):
        """Return a reference to the hops list for the message."""
        hops = self._msg['routing_metadata'].setdefault('go_hops', [])
        return hops

    def set_hops(self, hops):
        """Set the hops list for the message."""
        self._msg['routing_metadata']['go_hops'] = hops[:]

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

    def next_router_endpoint(self):
        """Computes the next endpoint to dispatch this message to from a router
        assuming this message is following the inverse of the hops contained in
        the cached outbound hops list.

        Returns the appropriate endpoint or `None` if no appropriate endpoint
        can be determined.
        """
        hops = self.get_hops()
        outbound_hops = self.get_outbound_hops()
        if hops is None or outbound_hops is None:
            return None
        if len(hops) > len(outbound_hops) - 1:
            return None
        [outbound_src, outbound_dst] = outbound_hops[-len(hops) - 1]
        return outbound_dst[1]

    def set_unroutable_reply(self):
        """
        Marks the message as a response to an unroutable inbound message
        or an event associated with such a response.
        """
        self._msg['routing_metadata']['is_reply_to_unroutable'] = True

    def get_unroutable_reply(self):
        """
        Returns whether the message is marked as a reply to an unroutable
        inbound message (or an event for such a reply).
        """
        return self._msg['routing_metadata'].get(
            'is_reply_to_unroutable', False)

    def unroutable_event_done(self):
        """
        Return True if the message is an event for an unroutable reply
        and its hops are done.
        """
        if not self.get_unroutable_reply():
            return False
        hops = self.get_hops()
        outbound_hops = self.get_outbound_hops()
        if not hops and not outbound_hops:
            # if hops and outbound hops are both either None or empty, consider
            # them equal
            return True
        if not hops or not outbound_hops:
            # if only one of hops or outbound hops are None or empty, consider
            # them not equal
            return False
        [dst, src] = hops[-1]
        [outbound_src, outbound_dst] = outbound_hops[0]
        return (dst == outbound_dst and src == outbound_src)


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
    billing_inbound_connector = ConfigText(
        "Connector to publish inbound messages on.",
        static=True, required=False)
    billing_outbound_connector = ConfigText(
        "Connector to publish outbound messages on.",
        static=True, required=False)
    user_account_key = ConfigText(
        "Key of the user account the message is from.")
    default_unroutable_inbound_reply = ConfigText(
        "Default text to send in response to unroutable inbound messages"
        " if the tagpool specifies `reply_to_unroutable_inbound` but not"
        " `unroutable_inbound_reply`.",
        default="Vumi Go could not route your message. Please try again soon.",
        static=True, required=False)
    account_cache_ttl = ConfigFloat(
        "TTL (in seconds) for cached accounts. If less than or equal to"
        " zero, routing tables will not be cached.",
        static=True, default=5)
    store_messages_to_transports = ConfigBool(
        "If true (the default), outbound messages to transports will be"
        " written to the message store.",
        static=True, default=True)
    optouts = ConfigDict(
        "Configuration options for the opt out helper",
        static=True, default={})


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
      * from: transports or routers
      * to: routers, conversations or the opt-out worker

    * outbound messages:
      * from: conversations, routers or the opt-out worker
      * to: routers or transports

    * events:
      * from: transports or routers
      * to: routers, conversations or the opt-out worker

    Further complexities arise because routers can be sources
    and destinations of both inbound and outbound messages (and events)
    so care has to be taken to keep track of which direction a message
    is travelling in in order to select the correct routing table
    entry when routing messages from dispatchers.

    Summary of how user account keys are determined:

    * for messages from transports:
      * tag is used to determine the user account id

    * for routers, conversations and the opt-out worker:
      * the user account id is read from the Vumi Go helper_metadata.

    When messages are published the following helper_metadata
    is included:

    * for transports: tag pool and tag name
    * for routers: user_account, router_type, router_key
    * for conversations: user_account, conversation_type, conversation_key
    * for the opt-out worker: user_account

    Messages received from these sources are expected to include the same
    metadata.
    """

    CONFIG_CLASS = AccountRoutingTableDispatcherConfig
    worker_name = 'account_routing_table_dispatcher'

    # connector types (references to GoConnector constants for convenience)
    CONVERSATION = GoConnector.CONVERSATION
    ROUTER = GoConnector.ROUTER
    TRANSPORT_TAG = GoConnector.TRANSPORT_TAG
    OPT_OUT = GoConnector.OPT_OUT
    BILLING = GoConnector.BILLING

    # directions (references to GoConnector constants for convenience)
    INBOUND = GoConnector.INBOUND
    OUTBOUND = GoConnector.OUTBOUND

    @inlineCallbacks
    def setup_dispatcher(self):
        yield super(AccountRoutingTableDispatcher, self).setup_dispatcher()
        yield self._go_setup_worker()
        config = self.get_static_config()
        self.account_cache = ModelObjectCache(
            reactor, config.account_cache_ttl)

        # Opt out and billing connectors
        self.opt_out_connector = config.opt_out_connector
        self.billing_inbound_connector = config.billing_inbound_connector
        self.billing_outbound_connector = config.billing_outbound_connector
        self.billing_connectors = set()
        self.billing_connectors.add(self.billing_inbound_connector)
        self.billing_connectors.add(self.billing_outbound_connector)

        # Router connectors
        self.router_inbound_connector_mapping = (
            config.router_inbound_connector_mapping)
        self.router_outbound_connector_mapping = (
            config.router_outbound_connector_mapping)
        self.router_connectors = set()
        self.router_connectors.update(
            config.router_inbound_connector_mapping.itervalues())
        self.router_connectors.update(
            config.router_outbound_connector_mapping.itervalues())

        # Application connectors
        self.application_connector_mapping = (
            config.application_connector_mapping)
        self.application_connectors = set(
            config.application_connector_mapping.itervalues())

        # Transport connectors
        self.transport_connectors = set(config.receive_inbound_connectors)
        self.transport_connectors -= self.router_connectors
        self.transport_connectors -= self.billing_connectors

        self.optouts = OptOutHelper(self.vumi_api, config.optouts)

    @inlineCallbacks
    def teardown_dispatcher(self):
        yield self.account_cache.cleanup()
        yield self._go_teardown_worker()
        yield super(AccountRoutingTableDispatcher, self).teardown_dispatcher()

    def get_user_account(self, user_api):
        """
        Get a user account object through the cache.
        """
        return self.account_cache.get_model(
            user_api.api.get_user_account, user_api.user_account_key)

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
            tag_info = yield msg_mdh.get_tag_info()
            user_account_key = tag_info.metadata['user_account']
            if user_account_key is None:
                raise UnownedTagError(
                    "Message received for unowned tag.", msg)
        else:
            raise UnroutableMessageError(
                "No user account key or tag on message", msg)

        user_api = self.get_user_api(user_account_key)
        account = yield self.get_user_account(user_api)
        routing_table = yield user_api.get_routing_table(account)

        config_dict = self.config.copy()
        config_dict['user_account_key'] = user_account_key
        config_dict['routing_table'] = routing_table._routing_table

        returnValue(self.CONFIG_CLASS(config_dict))

    def connector_type(self, connector_name):
        if connector_name in self.billing_connectors:
            return self.BILLING
        elif connector_name in self.application_connectors:
            return self.CONVERSATION
        elif connector_name in self.router_connectors:
            return self.ROUTER
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
            return self.router_outbound_connector_mapping.get(router_type)

    def router_direction(self, direction):
        """Converts an connector direction (as seen from the perspective of
        this app) into the direction as seen by a router (i.e. the
        reverse).
        """
        router_direction = {
            self.INBOUND: self.OUTBOUND,
            self.OUTBOUND: self.INBOUND,
        }.get(direction)
        return router_direction

    @inlineCallbacks
    def set_destination(self, msg, target, direction, push_hops=True):
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
                self.CONVERSATION, self.ROUTER, self.OPT_OUT, self.BILLING)
        else:
            allowed_types = (
                self.ROUTER, self.TRANSPORT_TAG, self.BILLING)

        if conn.ctype not in allowed_types:
            raise UnroutableMessageError(
                "Destination connector of invalid type: %s" % conn, msg)

        if conn.ctype == conn.CONVERSATION:
            msg_mdh.set_conversation_info(conn.conv_type, conn.conv_key)
            dst_connector_name = self.get_application_connector(conn.conv_type)

        elif conn.ctype == conn.ROUTER:
            msg_mdh.set_router_info(conn.router_type, conn.router_key)
            dst_connector_name = self.get_router_connector(
                conn.router_type, self.router_direction(direction))

        elif conn.ctype == conn.TRANSPORT_TAG:
            msg_mdh.set_tag([conn.tagpool, conn.tagname])
            tagpool_metadata = yield msg_mdh.get_tagpool_metadata()
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
            msg['transport_name'] = transport_name

            transport_type = tagpool_metadata.get('transport_type')
            if transport_type is not None:
                msg['transport_type'] = transport_type
            else:
                log.error(
                    "No transport type found for tagpool %r while routing %s"
                    % (conn.tagpool, msg))

        elif conn.ctype == conn.OPT_OUT:
            dst_connector_name = self.opt_out_connector

        elif conn.ctype == conn.BILLING:
            if direction == self.INBOUND:
                dst_connector_name = self.billing_inbound_connector
            else:
                dst_connector_name = self.billing_outbound_connector

        else:
            raise UnroutableMessageError(
                "Serious error. Reached apparently unreachable state"
                " in which destination connector type is valid but"
                " unknown. Bad connector is: %s" % conn, msg)

        if push_hops:
            rmeta = RoutingMetadata(msg)
            rmeta.push_destination(str(conn), target[1])
        returnValue((dst_connector_name, target[1]))

    def acquire_source(self, msg, connector_type, direction, push_hops=True):
        """Determine the `str(go_connector)` value that a msg came
        in on by looking at the connector_type and fetching the
        appropriate values from the `msg` helper_metadata.

        Raises `UnroutableMessageError` if the connector_type has a
        value not appropriate for the direction.

        Note: `str(go_connector)` is what is stored in Go routing tables.
        """
        msg_mdh = self.get_metadata_helper(msg)

        if direction == self.INBOUND:
            allowed_types = (self.TRANSPORT_TAG, self.ROUTER, self.BILLING)
        else:
            allowed_types = (self.CONVERSATION, self.ROUTER,
                             self.OPT_OUT, self.BILLING)

        if connector_type not in allowed_types:
            raise UnroutableMessageError(
                "Source connector of invalid type: %s" % connector_type, msg)

        if connector_type == self.CONVERSATION:
            conv_info = msg_mdh.get_conversation_info()
            src_conn = str(GoConnector.for_conversation(
                conv_info['conversation_type'], conv_info['conversation_key']))

        elif connector_type == self.ROUTER:
            router_info = msg_mdh.get_router_info()
            src_conn = str(GoConnector.for_router(
                router_info['router_type'], router_info['router_key'],
                self.router_direction(direction)))

        elif connector_type == self.TRANSPORT_TAG:
            src_conn = str(GoConnector.for_transport_tag(*msg_mdh.tag))

        elif connector_type == self.OPT_OUT:
            src_conn = str(GoConnector.for_opt_out())

        elif connector_type == self.BILLING:
            # when the source is a billing router, outbound messages
            # are always received from the inbound billing connector
            # and inbound messages are always received from the outbound
            # billing connector.
            src_conn = str(
                GoConnector.for_billing(self.router_direction(direction)))

        else:
            raise UnroutableMessageError(
                "Serious error. Reached apparently unreachable state"
                " in which source connector type is both valid"
                " but unknown. Bad connector type is: %s"
                % connector_type, msg)

        src_conn_str = str(src_conn)
        if push_hops:
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
    def tag_for_reply(self, reply):
        """Look up the original message and return its tag.

        Used to route replies from the opt-out worker back to the transport
        the original message came from.self

        Raises UnroutableMessageError if the tag cannout be determined.
        """
        orig_msg = yield self.find_message_for_reply(reply)
        if orig_msg is None:
            raise UnroutableMessageError(
                "Could not find original message for reply from"
                " the opt-out worker", reply)
        orig_msg_mdh = self.get_metadata_helper(orig_msg)
        if orig_msg_mdh.tag is None:
            raise UnroutableMessageError(
                "Could not find tag on original message for reply"
                " from the opt-out worker", reply)
        returnValue(orig_msg_mdh.tag)

    @inlineCallbacks
    def publish_outbound_optout(self, config, msg):
        """Publish a reply from the opt-out worker.

        It does this by looking up the original message and
        sending the reply out via the same tag the original
        message came in on.
        """
        tag = yield self.tag_for_reply(msg)
        dst_conn = GoConnector.for_transport_tag(*tag)
        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, [str(dst_conn), 'default'], self.OUTBOUND)
        yield self.publish_outbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
    def publish_inbound_to_billing(self, config, msg):
        """Publish an inbound message to the billing worker."""
        target = (str(GoConnector.for_billing(self.INBOUND)), 'default')
        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, target, self.INBOUND)

        yield self.publish_inbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
    def publish_outbound_to_billing(self, config, msg, tag):
        """Publish an outbound message to the billing worker."""
        msg_mdh = self.get_metadata_helper(msg)
        msg_mdh.set_tag(tag)
        target = (str(GoConnector.for_billing(self.OUTBOUND)), 'default')
        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, target, self.OUTBOUND)

        yield self.publish_outbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
    def publish_outbound_from_billing(self, config, msg):
        """Publish an outbound message to its intended destination
        after billing.
        """
        msg_mdh = self.get_metadata_helper(msg)
        dst_conn = GoConnector.for_transport_tag(*msg_mdh.tag)
        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, [str(dst_conn), 'default'], self.OUTBOUND)

        yield self.publish_outbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
    def publish_outbound(self, msg, connector_name, endpoint):
        """
        Publish an outbound message, storing it if necessary.

        We override the default outbound publisher here so we can write the
        outbound message to the message store where we need to.
        """
        if connector_name in self.transport_connectors:
            if self.get_static_config().store_messages_to_transports:
                yield self.vumi_api.mdb.add_outbound_message(msg)

        yield super(RoutingTableDispatcher, self).publish_outbound(
            msg, connector_name, endpoint)

    @inlineCallbacks
    def handle_unroutable_inbound_message(self, f, msg, connector_name):
        """Send a reply to the unroutable `msg` if the tagpool asks for one.

        If we can't find the tagpool or the tagpool isn't configured for
        replies to unroutable messages, the original exception is reraised.
        """
        msg_mdh = self.get_metadata_helper(msg)
        if msg_mdh.tag is None:
            # defend against messages without tags (these should not occur
            # but this is an error path)
            f.raiseException()

        tagpool_metadata = yield msg_mdh.get_tagpool_metadata()
        if not tagpool_metadata.get('reply_to_unroutable_inbound'):
            f.raiseException()

        config = self.get_static_config()
        default_response = config.default_unroutable_inbound_reply
        response = tagpool_metadata.get(
            'unroutable_inbound_reply', default_response)
        reply = msg.reply(response, continue_session=False)

        # re-acquire source connector information (hops already pushed)
        connector_type = self.connector_type(connector_name)
        src_conn = self.acquire_source(msg, connector_type, self.INBOUND,
                                       push_hops=False)
        # send it back from whence it came
        target = [src_conn, msg.get_routing_endpoint()]
        # no source hop on reply so don't push destination hop
        dst_connector_name, dst_endpoint = yield self.set_destination(
            reply, target, self.OUTBOUND, push_hops=False)
        # mark as an unroutable reply
        reply_rmeta = RoutingMetadata(reply)
        reply_rmeta.set_unroutable_reply()

        yield self.publish_outbound(
            reply, dst_connector_name, dst_endpoint)

    def errback_inbound(self, f, msg, connector_name):
        f.trap(*REPLYABLE_ERRORS)  # Reraise any other exception types.
        return self.handle_unroutable_inbound_message(f, msg, connector_name)

    @inlineCallbacks
    def process_inbound(self, config, msg, connector_name):
        """Process an inbound message.

        Inbound messages can be from:

        * transports (these might be opt-out messages)
        * routers
        * the billing worker

        And may go to:

        * routers
        * conversations
        * the opt-out worker
        * the billing worker
        """
        log.debug("Processing inbound: %r" % (msg,))

        user_api = self.get_user_api(config.user_account_key)
        account = yield self.get_user_account(user_api)
        yield self.optouts.process_message(account, msg)

        msg_mdh = self.get_metadata_helper(msg)
        msg_mdh.set_user_account(config.user_account_key)

        connector_type = self.connector_type(connector_name)
        src_conn = self.acquire_source(msg, connector_type, self.INBOUND)

        if self.billing_inbound_connector:
            if connector_type == self.TRANSPORT_TAG:
                yield self.publish_inbound_to_billing(config, msg)
                return
            if connector_type == self.BILLING:
                # set the src_conn to the transport and keep routing
                src_conn = str(GoConnector.for_transport_tag(*msg_mdh.tag))

        if msg_mdh.is_optout_message():
            yield self.publish_inbound_optout(config, msg)
            return

        target = self.find_target(config, msg, src_conn)
        if target is None:
            raise NoTargetError(
                "No target found for inbound message from %r"
                % (connector_name,), msg)

        dst_connector_name, dst_endpoint = yield self.set_destination(
            msg, target, self.INBOUND)

        yield self.publish_inbound(msg, dst_connector_name, dst_endpoint)

    @inlineCallbacks
    def process_outbound(self, config, msg, connector_name):
        """Process an outbound message.

        Outbound messages can be from:

        * conversations
        * routers
        * the opt-out worker
        * the billing worker

        And may go to:

        * routers
        * transports
        * the billing worker
        """
        log.debug("Processing outbound: %s" % (msg,))
        msg_mdh = self.get_metadata_helper(msg)
        msg_mdh.set_user_account(config.user_account_key)

        connector_type = self.connector_type(connector_name)
        src_conn = self.acquire_source(msg, connector_type, self.OUTBOUND)

        if self.billing_outbound_connector:
            if connector_type in (self.CONVERSATION, self.ROUTER):
                msg_mdh.reset_paid()
            elif connector_type == self.OPT_OUT:
                tag = yield self.tag_for_reply(msg)
                yield self.publish_outbound_to_billing(config, msg, tag)
                return
            elif connector_type == self.BILLING:
                yield self.publish_outbound_from_billing(config, msg)
                return
        else:
            if connector_type == self.OPT_OUT:
                yield self.publish_outbound_optout(config, msg)
                return

        target = self.find_target(config, msg, src_conn)
        if target is None:
            raise NoTargetError(
                "No target found for outbound message from '%s': %s" % (
                    connector_name, msg), msg)

        if self.billing_outbound_connector:
            target_conn = GoConnector.parse(target[0])
            if target_conn.ctype == target_conn.TRANSPORT_TAG:
                tag = [target_conn.tagpool, target_conn.tagname]
                yield self.publish_outbound_to_billing(config, msg, tag)
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
        msg_rmeta = RoutingMetadata(msg)
        msg_unroutable = msg_rmeta.get_unroutable_reply()

        msg_hops = msg_rmeta.get_hops()
        event_rmeta.set_outbound_hops(msg_hops)

        if msg_unroutable:
            event_rmeta.set_unroutable_reply()

        if msg_mdh.tag is None:
            raise UnroutableMessageError(
                "Outbound message for event has no tag set: %r" % (msg,),
                event)
        # set the tag on the event so that if it is from a transport
        # we can set the source of the message correctly in acquire_source.
        event_mdh.set_tag(msg_mdh.tag)

        if not msg_unroutable or msg_hops:
            # unroutable replies without hops were never associated with a
            # user account and so aren't required to have one. All other
            # messages must.
            if not msg_mdh.has_user_account():
                raise UnroutableMessageError(
                    "Outbound message for event has no associated"
                    " user account: %r" % (msg,), event)
            event_mdh.set_user_account(msg_mdh.get_account_key())

    @inlineCallbacks
    def process_event(self, config, event, connector_name):
        """Process an event message.

        Events must trace back the path through the routers
        and conversations that was taken by the associated outbound
        message.

        Events thus ignore the routing table itself.

        Events can be from:

        * transports
        * routers

        And may go to:

        * routers
        * conversations
        * the opt-out worker
        """
        log.debug("Processing event: %s" % (event,))

        # events are in same direction as inbound messages so
        # we use INBOUND as the direction in this method.

        yield self._set_event_metadata(event)

        # events for unroutable messages that have completed their hops
        # don't need to be processed further.
        rmeta = RoutingMetadata(event)
        if rmeta.unroutable_event_done():
            return

        connector_type = self.connector_type(connector_name)
        # we ignore the source connector returned but .acquire_source() sets
        # the initial hop and .next_hop() checks that it matches the outbound
        # destination.
        self.acquire_source(event, connector_type, self.INBOUND)

        target = rmeta.next_hop()
        if target is None:
            raise UnroutableMessageError(
                "Could not find next hop for event.", event)

        dst_connector_name, dst_endpoint = yield self.set_destination(
            event, target, self.INBOUND)
        yield self.publish_event(event, dst_connector_name, dst_endpoint)
