# -*- test-case-name: go.apps.opt_out.tests.test_vumi_app -*-

from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import ForeignKey, Timestamp, Unicode

from go.vumitools.account import UserAccount, PerAccountStore


class OptOut(Model):
    """An opt_out"""
    user_account = ForeignKey(UserAccount)
    message = Unicode(null=True)
    created_at = Timestamp(default=datetime.utcnow)


class OptOutStore(PerAccountStore):
    def setup_proxies(self):
        self.opt_outs = self.manager.proxy(OptOut)

    def opt_out_id(self, addr_type, addr_value):
        return "%s:%s" % (addr_type, addr_value)

    @Manager.calls_manager
    def new_opt_out(self, addr_type, addr_value, message):
        opt_out_id = self.opt_out_id(addr_type, addr_value)
        opt_out = self.opt_outs(opt_out_id,
                user_account=self.user_account_key,
                message=message.get('message_id'))
        yield opt_out.save()
        returnValue(opt_out)

    def get_opt_out(self, addr_type, addr_value):
        return self.opt_outs.load(self.opt_out_id(addr_type, addr_value))

    @Manager.calls_manager
    def delete_opt_out(self, addr_type, addr_value):
        opt_out = yield self.get_opt_out(addr_type, addr_value)
        if opt_out:
            yield opt_out.delete()

    def list_opt_outs(self):
        return self.list_keys(self.opt_outs)

    def opt_outs_for_addresses(self, addr_type, addresses):
        keys = ["%s:%s" % (addr_type, address) for address in addresses]
        mr = self.manager.mr_from_keys(self.opt_outs, keys)
        mr.filter_not_found()
        return mr.get_keys()
