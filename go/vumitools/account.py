# -*- test-case-name: go.vumitools.tests.test_contact -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import Unicode, Timestamp


class UserAccount(Model):
    """A user account."""
    # key is uuid
    username = Unicode(max_length=255)
    created_at = Timestamp(default=datetime.utcnow)


class AccountStore(object):
    def __init__(self, manager):
        self.manager = manager
        self.users = self.manager.proxy(UserAccount)

    @Manager.calls_manager
    def new_user(self, username):
        key = uuid4().get_hex()
        user = self.users(key, username=username)
        yield user.save()
        returnValue(user)

    def get_user(self, key):
        return self.users.load(key)


class PerAccountStore(object):
    def __init__(self, user_account):
        self.set_user(user_account)

    @classmethod
    def from_django_user(cls, user):
        """Convenience constructor for using this from Django."""
        return cls(user.userprofile.get_user_account())

    def set_user(self, user_account):
        self.base_manager = user_account.manager
        self.user_account = user_account
        self.manager = self.base_manager.sub_manager(user_account.key)
        self.setup_proxies()

    def get_user_account(self):
        store = AccountStore(self.base_manager)
        return store.users.load(self.user_account.key)

    def setup_proxies(self):
        pass
