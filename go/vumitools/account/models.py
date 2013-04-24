# -*- test-case-name: go.vumitools.tests.test_contact -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi import log
from vumi.persist.model import Model, Manager
from vumi.persist.fields import (
   Integer, Unicode, Timestamp, ManyToMany, Json, Boolean)

from go.vumitools.account.migrations import UserAccountMigrator


class UserTagPermission(Model):
    """A description of a tag a user account is allowed access to."""
    # key is uuid
    tagpool = Unicode(max_length=255)
    max_keys = Integer(null=True)


class UserAppPermission(Model):
    """An application that provides a certain conversation_type"""
    application = Unicode(max_length=255)


class UserAccount(Model):
    """A user account."""

    VERSION = 2
    MIGRATOR = UserAccountMigrator

    # key is uuid
    username = Unicode(max_length=255)
    # TODO: tagpools can be made OneToMany once vumi.persist.fields
    #       gains a OneToMany field
    tagpools = ManyToMany(UserTagPermission)
    applications = ManyToMany(UserAppPermission)
    created_at = Timestamp(default=datetime.utcnow)
    event_handler_config = Json(default=list)
    msisdn = Unicode(max_length=255, null=True)
    confirm_start_conversation = Boolean(default=False)
    email_summary = Unicode(max_length=255, null=True)
    # `tags` is allowed to be null so that we can detect freshly-migrated
    # accounts and populate the tags from active conversations. A new account
    # has no legacy tags or conversations, so we start with an empty list and
    # skip the tag collection.
    tags = Json(default=[], null=True)
    # `routing_table` is allowed to be null so that we can detect
    # freshly-migrated accounts and populate the routing table from active
    # conversations. A new account has no legacy conversations, so we start
    # with an empty dict and skip the table building.
    routing_table = Json(default={}, null=True)

    @Manager.calls_manager
    def has_tagpool_permission(self, tagpool):
        for tp_bunch in self.tagpools.load_all_bunches():
            for tp in (yield tp_bunch):
                if tp.tagpool == tagpool:
                    returnValue(True)
        returnValue(False)


class RoutingTableHelper(object):
    """Helper for dealing with routing table dictionaries.

    Conceptually a routing table maps (source_connector, source_endpoint) pairs
    to (destination_connector, destination_endpoint) pairs.

    Internally this is implemented as a nested mapping::

        source_connector ->
            source_endpoint_1 -> [destination_connector, destination_endpoint]
            source_endpoint_2 -> [..., ...]

    in order to make storing the mapping as JSON easier (JSON keys cannot be
    lists).
    """

    def __init__(self, routing_table):
        self.routing_table = routing_table

    def lookup_target(self, src_conn, src_endpoint):
        return self.routing_table.get(src_conn, {}).get(src_endpoint)

    def add_entry(self, src_conn, src_endpoint, dst_conn, dst_endpoint):
        connector_dict = self.routing_table.setdefault(src_conn, {})
        if src_endpoint in connector_dict:
            log.warning(
                "Replacing routing entry for (%r, %r): was %r, now %r" % (
                    src_conn, src_endpoint, connector_dict[src_endpoint],
                    [dst_conn, dst_endpoint]))
        connector_dict[src_endpoint] = [dst_conn, dst_endpoint]

    def remove_entry(self, src_conn, src_endpoint):
        connector_dict = self.routing_table.get(src_conn)
        if connector_dict is None or src_endpoint not in connector_dict:
            log.warning(
                "Attempting to remove missing routing entry for (%r, %r)." % (
                    src_conn, src_endpoint))
            return None

        old_dest = connector_dict.pop(src_endpoint)

        if not connector_dict:
            # This is the last entry for this connector
            self.routing_table.pop(src_conn)

        return old_dest

    def remove_connector(self, conn):
        """Remove all references to the given connector.

        Useful when the connector is going away for some reason.
        """
        # remove entries with connector as source
        self.routing_table.pop(conn, None)

        # remove entires with connector as destination
        to_remove = []
        for src_conn, routes in self.routing_table.iteritems():
            for src_endpoint, (dest_conn, dest_endpoint) in routes.items():
                if dest_conn == conn:
                    del routes[src_endpoint]
            if not routes:
                # We can't modify this dict while iterating over it.
                to_remove.append(src_conn)

        for src_conn in to_remove:
            del self.routing_table[src_conn]

    def remove_conversation(self, conv):
        """Remove all entries linking to or from a given conversation.

        Useful when arching a conversation to ensure it is no longer
        present in the routing table.
        """
        conv_conn = str(GoConnector.for_conversation(conv.conversation_type,
                                                     conv.key))
        self.remove_connector(conv_conn)

    def add_oldstyle_conversation(self, conv, tag, outbound_only=False):
        """XXX: This can be removed when old-style conversations are gone."""
        conv_conn = str(GoConnector.for_conversation(conv.conversation_type,
                                                     conv.key))
        tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
        self.add_entry(conv_conn, "default", tag_conn, "default")
        if not outbound_only:
            self.add_entry(tag_conn, "default", conv_conn, "default")


class GoConnectorError(Exception):
    """Raised when attempting to construct an invalid connector."""


class GoConnector(object):
    """Container for Go routing table connector item."""

    # Types of connectors in Go routing tables

    CONVERSATION = "CONVERSATION"
    ROUTING_BLOCK = "ROUTING_BLOCK"
    TRANSPORT_TAG = "TRANSPORT_TAG"

    def __init__(self, ctype, names, parts):
        self.ctype = ctype
        self._names = names
        self._parts = parts
        self._attrs = dict(zip(self._names, self._parts))

    def __str__(self):
        return ":".join([self.ctype] + self._parts)

    def __getattr__(self, name):
        return self._attrs[name]

    @classmethod
    def for_conversation(cls, conv_type, conv_key):
        return cls(cls.CONVERSATION, ["conv_type", "conv_key"],
                   [conv_type, conv_key])

    @classmethod
    def for_routing_block(cls, rblock_type, rblock_key):
        return cls(cls.ROUTING_BLOCK, ["rblock_type", "rblock_key"],
                   [rblock_type, rblock_key])

    @classmethod
    def for_transport_tag(cls, tagpool, tagname):
        return cls(cls.TRANSPORT_TAG, ["tagpool", "tagname"],
                   [tagpool, tagname])

    @classmethod
    def parse(cls, s):
        parts = s.split(":")
        ctype, parts = parts[0], parts[1:]
        constructors = {
            cls.CONVERSATION: cls.for_conversation,
            cls.ROUTING_BLOCK: cls.for_routing_block,
            cls.TRANSPORT_TAG: cls.for_transport_tag,
        }
        if ctype not in constructors:
            raise GoConnectorError("Unknown connector type %r"
                                   " found while parsing: %r" % (ctype, s))
        try:
            return constructors[ctype](*parts)
        except TypeError:
            raise GoConnectorError("Invalid connector of type %r: %r"
                                   % (ctype, s))


class AccountStore(object):
    def __init__(self, manager):
        self.manager = manager
        self.users = self.manager.proxy(UserAccount)
        self.tag_permissions = self.manager.proxy(UserTagPermission)
        self.application_permissions = self.manager.proxy(UserAppPermission)

    @Manager.calls_manager
    def new_user(self, username):
        key = uuid4().get_hex()
        user = self.users(key, username=username)
        yield user.save()
        returnValue(user)

    def get_user(self, key):
        return self.users.load(key)


class PerAccountStore(object):
    def __init__(self, base_manager, user_account_key):
        self.base_manager = base_manager
        self.user_account_key = user_account_key
        self.manager = self.base_manager.sub_manager(user_account_key)
        self.setup_proxies()

    @classmethod
    def from_django_user(cls, user):
        """Convenience constructor for using this from Django."""
        user_account = user.userprofile.get_user_account()
        return cls.from_user_account(user_account)

    @classmethod
    def from_user_account(cls, user_account):
        """Convenience constructor for using this a UserAccount."""
        return cls(user_account.manager, user_account.key)

    def get_user_account(self):
        store = AccountStore(self.base_manager)
        return store.users.load(self.user_account_key)

    def setup_proxies(self):
        pass
