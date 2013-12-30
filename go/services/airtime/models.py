from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import Unicode, ForeignKey, Timestamp, Json, ListOf

from go.vumitools.account import UserAccount, PerAccountStore


class VoucherPool(Model):
    """A pool for airtime vouchers"""

    VERSION = 1

    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255)
    config = Json(default=dict)
    created_at = Timestamp(default=datetime.utcnow, index=True)
    imports = ListOf(Unicode())


class VoucherPoolStore(PerAccountStore):
    def setup_proxies(self):
        self.voucher_pools = self.manager.proxy(VoucherPool)

    def list_voucher_pools(self):
        voucher_pool_list = []
        for key in self.list_keys(self.voucher_pools):
            voucher_pool_list.append(self.get_voucher_pool_by_key(key))
        return voucher_pool_list

    def get_voucher_pool_by_key(self, key):
        return self.voucher_pools.load(key)

    @Manager.calls_manager
    def new_voucher_pool(self, name, config, **fields):
        voucher_pool_id = uuid4().get_hex()
        voucher_pool = self.voucher_pools(
            voucher_pool_id, user_account=self.user_account_key, name=name,
            config=config, **fields)

        voucher_pool = yield voucher_pool.save()
        returnValue(voucher_pool)
