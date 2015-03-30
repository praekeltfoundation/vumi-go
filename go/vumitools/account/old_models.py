from datetime import datetime
from uuid import uuid4

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import (
    Integer, Unicode, Timestamp, ManyToMany, Json, Boolean)

from go.vumitools.account.fields import RoutingTableField
from go.vumitools.account.migrations import UserAccountMigrator
from go.vumitools.routing_table import RoutingTable


class UserTagPermissionVNone(Model):
    """A description of a tag a user account is allowed access to."""
    bucket = "usertagpermission"

    # key is uuid
    tagpool = Unicode(max_length=255)
    max_keys = Integer(null=True)


class UserAppPermissionVNone(Model):
    """An application that provides a certain conversation_type"""
    bucket = "userapppermission"

    application = Unicode(max_length=255)


class UserAccountVNone(Model):
    """A user account."""
    bucket = "useraccount"

    # key is uuid
    username = Unicode(max_length=255)
    tagpools = ManyToMany(UserTagPermissionVNone)
    applications = ManyToMany(UserAppPermissionVNone)
    created_at = Timestamp(default=datetime.utcnow)
    event_handler_config = Json(null=True)
    msisdn = Unicode(max_length=255, null=True)
    confirm_start_conversation = Boolean(default=False)


class AccountStoreVNone(object):
    def __init__(self, manager):
        self.manager = manager
        self.users = self.manager.proxy(UserAccountVNone)
        self.tag_permissions = self.manager.proxy(UserTagPermissionVNone)
        self.application_permissions = self.manager.proxy(
            UserAppPermissionVNone)

    @Manager.calls_manager
    def new_user(self, username):
        key = uuid4().get_hex()
        user = self.users(key, username=username)
        yield user.save()
        returnValue(user)

    def get_user(self, key):
        return self.users.load(key)


class UserAccountV1(Model):
    """A user account."""

    bucket = "useraccount"
    VERSION = 1
    MIGRATOR = UserAccountMigrator

    # key is uuid
    username = Unicode(max_length=255)
    tagpools = ManyToMany(UserTagPermissionVNone)
    applications = ManyToMany(UserAppPermissionVNone)
    created_at = Timestamp(default=datetime.utcnow)
    event_handler_config = Json(default=list)
    msisdn = Unicode(max_length=255, null=True)
    confirm_start_conversation = Boolean(default=False)
    # `tags` is allowed to be null so that we can detect freshly-migrated
    # accounts and populate the tags from active conversations. A new account
    # has no legacy tags or conversations, so we start with an empty list and
    # skip the tag collection.
    tags = Json(default=[], null=True)

    @Manager.calls_manager
    def has_tagpool_permission(self, tagpool):
        for tp_bunch in self.tagpools.load_all_bunches():
            for tp in (yield tp_bunch):
                if tp.tagpool == tagpool:
                    returnValue(True)
        returnValue(False)


class AccountStoreV1(object):
    def __init__(self, manager):
        self.manager = manager
        self.users = self.manager.proxy(UserAccountV1)
        self.tag_permissions = self.manager.proxy(UserTagPermissionVNone)
        self.application_permissions = self.manager.proxy(
            UserAppPermissionVNone)

    @Manager.calls_manager
    def new_user(self, username):
        key = uuid4().get_hex()
        user = self.users(key, username=username)
        yield user.save()
        returnValue(user)

    def get_user(self, key):
        return self.users.load(key)


class UserAccountV2(Model):
    """A user account."""

    bucket = "useraccount"
    VERSION = 2
    MIGRATOR = UserAccountMigrator

    # key is uuid
    username = Unicode(max_length=255)
    tagpools = ManyToMany(UserTagPermissionVNone)
    applications = ManyToMany(UserAppPermissionVNone)
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


class UserAccountV3(Model):
    """A user account."""

    bucket = "useraccount"
    VERSION = 3
    MIGRATOR = UserAccountMigrator

    # key is uuid
    username = Unicode(max_length=255)
    tagpools = ManyToMany(UserTagPermissionVNone)
    applications = ManyToMany(UserAppPermissionVNone)
    created_at = Timestamp(default=datetime.utcnow)
    event_handler_config = Json(default=list)
    msisdn = Unicode(max_length=255, null=True)
    confirm_start_conversation = Boolean(default=False)
    email_summary = Unicode(max_length=255, null=True)
    tags = Json(default=[])
    routing_table = RoutingTableField(default=RoutingTable({}))

    @Manager.calls_manager
    def has_tagpool_permission(self, tagpool):
        for tp_bunch in self.tagpools.load_all_bunches():
            for tp in (yield tp_bunch):
                if tp.tagpool == tagpool:
                    returnValue(True)
        returnValue(False)


class UserAccountV4(Model):
    """A user account."""

    bucket = "useraccount"
    VERSION = 4
    MIGRATOR = UserAccountMigrator

    # key is uuid
    username = Unicode(max_length=255)
    tagpools = ManyToMany(UserTagPermissionVNone)
    applications = ManyToMany(UserAppPermissionVNone)
    created_at = Timestamp(default=datetime.utcnow)
    event_handler_config = Json(default=list)
    msisdn = Unicode(max_length=255, null=True)
    confirm_start_conversation = Boolean(default=False)
    can_manage_optouts = Boolean(default=False)
    email_summary = Unicode(max_length=255, null=True)
    tags = Json(default=[])
    routing_table = RoutingTableField(default=RoutingTable({}))

    @Manager.calls_manager
    def has_tagpool_permission(self, tagpool):
        for tp_bunch in self.tagpools.load_all_bunches():
            for tp in (yield tp_bunch):
                if tp.tagpool == tagpool:
                    returnValue(True)
        returnValue(False)


class UserAccountV5(Model):
    """A user account."""

    bucket = "useraccount"
    VERSION = 5
    MIGRATOR = UserAccountMigrator

    # key is uuid
    username = Unicode(max_length=255)
    tagpools = ManyToMany(UserTagPermissionVNone)
    applications = ManyToMany(UserAppPermissionVNone)
    created_at = Timestamp(default=datetime.utcnow)
    event_handler_config = Json(default=list)
    msisdn = Unicode(max_length=255, null=True)
    confirm_start_conversation = Boolean(default=False)
    disable_optouts = Boolean(default=False)
    can_manage_optouts = Boolean(default=False)
    email_summary = Unicode(max_length=255, null=True)
    tags = Json(default=[])
    routing_table = RoutingTableField(default=RoutingTable({}))

    @Manager.calls_manager
    def has_tagpool_permission(self, tagpool):
        for tp_bunch in self.tagpools.load_all_bunches():
            for tp in (yield tp_bunch):
                if tp.tagpool == tagpool:
                    returnValue(True)
        returnValue(False)


class AccountStoreV2(object):
    def __init__(self, manager):
        self.manager = manager
        self.users = self.manager.proxy(UserAccountV2)
        self.tag_permissions = self.manager.proxy(UserTagPermissionVNone)
        self.application_permissions = self.manager.proxy(
            UserAppPermissionVNone)

    @Manager.calls_manager
    def new_user(self, username):
        key = uuid4().get_hex()
        user = self.users(key, username=username)
        yield user.save()
        returnValue(user)

    def get_user(self, key):
        return self.users.load(key)


class AccountStoreV4(object):
    def __init__(self, manager):
        self.manager = manager
        self.users = self.manager.proxy(UserAccountV4)
        self.tag_permissions = self.manager.proxy(UserTagPermissionVNone)
        self.application_permissions = self.manager.proxy(
            UserAppPermissionVNone)

    @Manager.calls_manager
    def new_user(self, username):
        key = uuid4().get_hex()
        user = self.users(key, username=username)
        yield user.save()
        returnValue(user)

    def get_user(self, key):
        return self.users.load(key)


class AccountStoreV5(object):
    def __init__(self, manager):
        self.manager = manager
        self.users = self.manager.proxy(UserAccountV5)
        self.tag_permissions = self.manager.proxy(UserTagPermissionVNone)
        self.application_permissions = self.manager.proxy(
            UserAppPermissionVNone)

    @Manager.calls_manager
    def new_user(self, username):
        key = uuid4().get_hex()
        user = self.users(key, username=username)
        yield user.save()
        returnValue(user)

    def get_user(self, key):
        return self.users.load(key)
