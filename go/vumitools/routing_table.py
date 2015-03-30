from vumi import log

from go.errors import VumiGoError


class GoRoutingTableError(VumiGoError):
    """Exception class for invalid operations on routing tables."""


class GoConnectorError(GoRoutingTableError):
    """Raised when attempting to construct an invalid connector."""


class GoConnector(object):
    """Container for Go routing table connector item."""

    # Types of connectors in Go routing tables

    CONVERSATION = "CONVERSATION"
    ROUTER = "ROUTER"
    TRANSPORT_TAG = "TRANSPORT_TAG"
    OPT_OUT = "OPT_OUT"
    BILLING = "BILLING"

    # Directions for router entries

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"

    def __init__(self, ctype, names, parts):
        self.ctype = ctype
        self._names = names
        self._parts = parts
        self._attrs = dict(zip(self._names, self._parts))

    @property
    def direction(self):
        return {
            self.OPT_OUT: self.INBOUND,
            self.CONVERSATION: self.INBOUND,
            self.TRANSPORT_TAG: self.OUTBOUND,
            self.ROUTER: self._attrs.get('direction'),
            self.BILLING: self._attrs.get('direction'),
        }[self.ctype]

    def __str__(self):
        return ":".join([self.ctype] + self._parts)

    def __repr__(self):
        return "<GoConnector: %r>" % str(self)

    def __eq__(self, other):
        if not isinstance(other, GoConnector):
            return False
        return str(self) == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __cmp__(self, other):
        if self == other:
            return 0
        if str(self) < str(other):
            return -1
        return 1

    def __hash__(self):
        return hash(str(self))

    def __getattr__(self, name):
        return self._attrs[name]

    def flip_direction(self):
        if self.ctype != self.ROUTER:
            raise GoConnectorError(
                "Attempt to call .flip_direction on %r which is not a router"
                " connector." % (self,))
        direction = (self.INBOUND if self.direction == self.OUTBOUND
                     else self.OUTBOUND)
        return GoConnector.for_router(
            self.router_type, self.router_key, direction)

    @classmethod
    def for_conversation(cls, conv_type, conv_key):
        return cls(cls.CONVERSATION, ["conv_type", "conv_key"],
                   [conv_type, conv_key])

    @classmethod
    def for_router(cls, router_type, router_key, direction):
        if direction not in (cls.INBOUND, cls.OUTBOUND):
            raise GoConnectorError(
                "Invalid connector direction: %s" % (direction,))
        return cls(cls.ROUTER,
                   ["router_type", "router_key", "direction"],
                   [router_type, router_key, direction])

    @classmethod
    def for_transport_tag(cls, tagpool, tagname):
        return cls(cls.TRANSPORT_TAG, ["tagpool", "tagname"],
                   [tagpool, tagname])

    @classmethod
    def for_opt_out(cls):
        return cls(cls.OPT_OUT, [], [])

    @classmethod
    def for_billing(cls, direction):
        if direction not in (cls.INBOUND, cls.OUTBOUND):
            raise GoConnectorError(
                "Invalid connector direction: %s" % (direction,))

        return cls(cls.BILLING, ["direction"], [direction])

    @classmethod
    def parse(cls, s):
        parts = s.split(":")
        ctype, parts = parts[0], parts[1:]
        constructors = {
            cls.CONVERSATION: cls.for_conversation,
            cls.ROUTER: cls.for_router,
            cls.TRANSPORT_TAG: cls.for_transport_tag,
            cls.OPT_OUT: cls.for_opt_out,
            cls.BILLING: cls.for_billing
        }
        if ctype not in constructors:
            raise GoConnectorError("Unknown connector type %r"
                                   " found while parsing: %r" % (ctype, s))
        try:
            return constructors[ctype](*parts)
        except TypeError:
            raise GoConnectorError("Invalid connector of type %r: %r"
                                   % (ctype, s))

    @classmethod
    def for_model(cls, model_obj, direction=None):
        """Construct an appropriate connector based on a model object.
        """
        if hasattr(model_obj, 'router_type'):
            return cls.for_router(
                model_obj.router_type, model_obj.key, direction)

        if direction is not None:
            raise GoConnectorError("Only router connectors have a direction.")

        if hasattr(model_obj, 'conversation_type'):
            return cls.for_conversation(
                model_obj.conversation_type, model_obj.key)

        # Hacky, replace when we have proper channels.
        if hasattr(model_obj, 'tagpool') and hasattr(model_obj, 'tag'):
            return cls.for_transport_tag(model_obj.tagpool, model_obj.tag)

        raise GoConnectorError(
            "Unknown object type for connector: %s" % (model_obj,))


def _to_conn(conn):
    if not isinstance(conn, GoConnector):
        conn = GoConnector.parse(conn)
    return conn


class RoutingTable(object):
    """Interface to routing table dictionaries.

    Conceptually a routing table maps (source_connector, source_endpoint) pairs
    to (destination_connector, destination_endpoint) pairs.

    Internally this is implemented as a nested mapping::

        source_connector ->
            source_endpoint_1 -> [destination_connector, destination_endpoint]
            source_endpoint_2 -> [..., ...]

    in order to make storing the mapping as JSON easier (JSON keys cannot be
    lists).
    """

    def __init__(self, routing_table=None):
        if routing_table is None:
            routing_table = {}
        self._routing_table = routing_table

    def __eq__(self, other):
        if not isinstance(other, RoutingTable):
            return False
        return self._routing_table == other._routing_table

    def __nonzero__(self):
        return bool(self._routing_table)

    def lookup_target(self, src_conn, src_endpoint):
        target = self._routing_table.get(str(src_conn), {}).get(src_endpoint)
        if target is not None:
            conn, ep = target
            target = [_to_conn(conn), ep]
        return target

    def lookup_targets(self, src_conn):
        targets = []
        for ep, dst in self._routing_table.get(str(src_conn), {}).iteritems():
            dst_str, dst_ep = dst
            targets.append((ep, [_to_conn(dst_str), dst_ep]))
        return targets

    def lookup_source(self, target_conn, target_endpoint):
        target_conn = _to_conn(target_conn)
        for src_conn, src_endpoint, dst_conn, dst_endpoint in self.entries():
            if dst_conn == target_conn and dst_endpoint == target_endpoint:
                return [src_conn, src_endpoint]
        return None

    def lookup_sources(self, target_conn):
        target_conn = _to_conn(target_conn)
        sources = []
        for src_conn, src_endpoint, dst_conn, dst_endpoint in self.entries():
            if dst_conn == target_conn:
                sources.append((dst_endpoint, [src_conn, src_endpoint]))
        return sources

    def entries(self):
        """Iterate over entries in the routing table.

        Yield tuples of (src_conn, src_endpoint, dst_conn, dst_endpoint).
        """
        for src_conn, endpoints in self._routing_table.iteritems():
            for src_endp, (dst_conn, dst_endp) in endpoints.iteritems():
                yield (
                    _to_conn(src_conn), src_endp, _to_conn(dst_conn), dst_endp)

    def add_entry(self, src_conn, src_endpoint, dst_conn, dst_endpoint):
        src_conn = _to_conn(src_conn)
        dst_conn = _to_conn(dst_conn)
        self.validate_entry(src_conn, src_endpoint, dst_conn, dst_endpoint)
        connector_dict = self._routing_table.setdefault(str(src_conn), {})
        if src_endpoint in connector_dict:
            log.info(
                "Replacing routing entry for (%r, %r): was %r, now %r" % (
                    str(src_conn), src_endpoint, connector_dict[src_endpoint],
                    [str(dst_conn), dst_endpoint]))
        connector_dict[src_endpoint] = [str(dst_conn), dst_endpoint]

    def remove_entry(self, src_conn, src_endpoint):
        src_conn = _to_conn(src_conn)
        src_str = str(src_conn)
        connector_dict = self._routing_table.get(src_str)
        if connector_dict is None or src_endpoint not in connector_dict:
            log.warning(
                "Attempting to remove missing routing entry for (%r, %r)." % (
                    src_str, src_endpoint))
            return None

        old_dest = connector_dict.pop(src_endpoint)

        if not connector_dict:
            # This is the last entry for this connector
            self._routing_table.pop(src_str)

        return old_dest

    def remove_endpoint(self, conn, endpoint):
        src = self.lookup_source(conn, endpoint)

        if src is not None:
            self.remove_entry(*src)

        self.remove_entry(conn, endpoint)

    def remove_connector(self, conn):
        """Remove all references to the given connector.

        Useful when the connector is going away for some reason.
        """
        conn = _to_conn(conn)
        # remove entries with connector as source
        self._routing_table.pop(str(conn), None)

        # remove entires with connector as destination
        to_remove = []
        for src_str, routes in self._routing_table.iteritems():
            for src_endpoint, (dst_str, dst_endpoint) in routes.items():
                if dst_str == str(conn):
                    del routes[src_endpoint]
            if not routes:
                # We can't modify this dict while iterating over it.
                to_remove.append(src_str)

        for src_str in to_remove:
            del self._routing_table[src_str]

    def remove_conversation(self, conv):
        """Remove all entries linking to or from a given conversation.

        Useful when archiving a conversation to ensure it is no longer
        present in the routing table.
        """
        self.remove_connector(conv.get_connector())

    def remove_router(self, router):
        """Remove all entries linking to or from a given router.

        Useful when archiving a router to ensure it is no longer present in the
        routing table.
        """
        self.remove_connector(router.get_inbound_connector())
        self.remove_connector(router.get_outbound_connector())

    def remove_transport_tag(self, tag):
        """Remove all entries linking to or from a given transport tag.

        Useful when releasing a tag to ensure it is no longer present in the
        routing table.
        """
        tag_conn = GoConnector.for_transport_tag(tag[0], tag[1])
        self.remove_connector(tag_conn)

    def transitive_targets(self, src_conn):
        """Return all connectors that are reachable from `src_conn`.

        Only follows routing steps from source to destination (never
        follows steps backwards from destination to source).

        Once a destination has been found, the following items are
        added to the list of things to search:

        * If the destination is a conversation, channel or opt-out
          connector no extra sources to search are added.

        * If the destination is a router, the connector on the other
          side of the router is added to the list of sources to search
          from (i.e. the inbound side if an outbound router connector
          is the target and vice versa).

        :param str src_conn: source connector to start search with.
        :rtype: set of destination connector strings.
        """
        src_conn = _to_conn(src_conn)
        sources = [src_conn]
        sources_seen = set(sources)
        results = set()
        while sources:
            source = sources.pop()
            destinations = self.lookup_targets(source)
            for _src_endpoint, (dst_conn, _dst_endpoint) in destinations:
                results.add(dst_conn)
                if dst_conn.ctype != GoConnector.ROUTER:
                    continue
                extra_src = str(dst_conn.flip_direction())
                if extra_src not in sources_seen:
                    sources.append(extra_src)
                    sources_seen.add(extra_src)
        return results

    def transitive_sources(self, dst_conn):
        """Return all connectors that lead to `dst_conn`.

        Only follows routing steps backwards from destination to
        source (never forwards from source to destination).

        Once a source has been found, the following items are
        added to the list of things to search:

        * If the sources is a conversation, channel or opt-out
          connector no extra destinations to search are added.

        * If the source is a router, the connector on the other side
          of the router is added to the list of destinations to search
          from (i.e. the inbound side if an outbound router connector
          is the source and vice versa).

        :param str dst_conn: destination connector to start search with.
        :rtype: set of source connector strings.
        """
        dst_conn = _to_conn(dst_conn)
        destinations = [dst_conn]
        destinations_seen = set(destinations)
        results = set()
        while destinations:
            destination = destinations.pop()
            sources = self.lookup_sources(destination)
            for _dst_endpoint, (src_conn, _src_endpoint) in sources:
                results.add(src_conn)
                if src_conn.ctype != GoConnector.ROUTER:
                    continue
                extra_dst = str(src_conn.flip_direction())
                if extra_dst not in destinations_seen:
                    destinations.append(extra_dst)
                    destinations_seen.add(extra_dst)
        return results

    def validate_entry(self, src_conn, src_endpoint, dst_conn, dst_endpoint):
        """Validate the provided entry.

        This method currently only validates that the source and destination
        have opposite directionality (IN->OUT or OUT->IN).
        """
        src_conn = _to_conn(src_conn)
        dst_conn = _to_conn(dst_conn)
        if src_conn.direction == dst_conn.direction:
            raise ValueError(
                "Invalid routing table entry: %s source (%s, %s) maps to %s"
                " destination (%s, %s)" % (
                    src_conn.direction, str(src_conn), src_endpoint,
                    dst_conn.direction, str(dst_conn), dst_endpoint))

    def validate_all_entries(self):
        """Validates all entries in the routing table.
        """
        for entry in self.entries():
            self.validate_entry(*entry)
