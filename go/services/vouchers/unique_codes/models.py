from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import Unicode, ForeignKey, Timestamp, Json, ListOf

from go.vumitools.account import UserAccount, PerAccountStore


class UniqueCodePool(Model):
    """A pool for unique codes"""

    VERSION = 1

    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255)
    config = Json(default=dict)
    created_at = Timestamp(default=datetime.utcnow, index=True)
    imports = ListOf(Unicode())


class UniqueCodePoolStore(PerAccountStore):

    def setup_proxies(self):
        self.unique_code_pools = self.manager.proxy(UniqueCodePool)

    def list_pools(self):
        return self.list_keys(self.unique_code_pools)

    def get_pool_by_key(self, key):
        return self.unique_code_pools.load(key)

    def get_all_pools(self):
        pool_list = []
        for key in self.list_pools():
            pool_list.append(self.get_pool_by_key(key))

        return pool_list

    def get_pool_by_name(self, name):
        for key in self.list_pools():
            unique_code_pool = self.get_pool_by_key(key)
            if unique_code_pool.name == name:
                return unique_code_pool
        return None

    @Manager.calls_manager
    def new_pool(self, name, config, **fields):
        pool_id = uuid4().get_hex()
        unique_code_pool = self.unique_code_pools(
            pool_id, user_account=self.user_account_key, name=name,
            config=config, **fields)

        unique_code_pool = yield unique_code_pool.save()
        returnValue(unique_code_pool)
