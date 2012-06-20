# -*- test-case-name: go.vumitools.tests.test_opt_out -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import (Unicode, ManyToMany, ForeignKey, Timestamp,
                                    Dynamic)

from go.vumitools.account import UserAccount, PerAccountStore


class OptOut(Model):
    """An opt_out"""
    user_account = ForeignKey(UserAccount)
    created_at = Timestamp(default=datetime.utcnow)


class OptOutStore(PerAccountStore):
    def setup_proxies(self):
        self.opt_outs = self.manager.proxy(OptOut)

    def opt_out_id(self, addr_type, addr_value):
        return "%s:%s" % (addr_type, addr_value)

    @Manager.calls_manager
    def new_opt_out(self, addr_type, addr_value):
        opt_out_id = self.opt_out_id(addr_type, addr_value)
        opt_out = self.opt_outs(
            opt_out_id, user_account=self.user_account_key)
        yield opt_out.save()
        returnValue(opt_out)

    def get_opt_out(self, addr_type, addr_value):
        return self.opt_outs.load(self.opt_out_id(addr_type, addr_value)

    @Manager.calls_manager
    def delete_opt_out(self, addr_type, addr_value):
        opt_out = yield self.get_opt_out(addr_type, addr_value)
        if opt_out:
            yield opt_out.delete()

    @Manager.calls_manager
    def list_opt_outs(self):
        # Not stale, because we're using backlinks.
        user_account = yield self.get_user_account()
        returnValue(user_account.backlinks.opt_outs(self.manager))
