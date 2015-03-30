# -*- test-case-name: go.vumitools.tests.test_contact -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import (
    Integer, Unicode, Timestamp, ManyToMany, Json, Boolean, SetOf)

from go.vumitools.account.fields import RoutingTableField
from go.vumitools.account.migrations import UserAccountMigrator
from go.vumitools.routing_table import RoutingTable


class UserTagPermission(Model):
    """A description of a tag a user account is allowed access to."""
    # key is uuid
    tagpool = Unicode(max_length=255)
    max_keys = Integer(null=True)


class UserAppPermission(Model):
    """An application that provides a certain conversation_type"""
    application = Unicode(max_length=255)


def flag_property(name):
    def fget(self):
        return name in self.flags

    def fset(self, value):
        if value:
            self.flags.add(name)
        else:
            self.flags.discard(name)

    return property(fget, fset)


class UserAccount(Model):
    """A user account."""

    VERSION = 6
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
    tags = Json(default=[])
    routing_table = RoutingTableField(default=RoutingTable({}))
    flags = SetOf(Unicode(), index=True)

    # Flag properties aren't the same as normal fields. Instead, they are just
    # some sugar for modifying the model's `flags` field. For this reason, we
    # don't need to bump the model version when adding a new flag property.
    can_manage_optouts = flag_property(u'can_manage_optouts')
    disable_optouts = flag_property(u'disable_optouts')
    is_developer = flag_property(u'is_developer')

    @Manager.calls_manager
    def has_tagpool_permission(self, tagpool):
        for tp_bunch in self.tagpools.load_all_bunches():
            for tp in (yield tp_bunch):
                if tp.tagpool == tagpool:
                    returnValue(True)
        returnValue(False)


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

    def list_keys(self, model_proxy, field_name='user_account'):
        return model_proxy.index_keys(field_name, self.user_account_key)

    def get_user_account(self):
        store = AccountStore(self.base_manager)
        return store.users.load(self.user_account_key)

    def setup_proxies(self):
        pass
