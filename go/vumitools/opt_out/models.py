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
        # this returns a Riak key which must be a binary string
        return (u"%s:%s" % (addr_type, addr_value)).encode('utf-8')

    @Manager.calls_manager
    def new_opt_out(self, addr_type, addr_value, message):
        opt_out_id = self.opt_out_id(addr_type, addr_value)
        message_id = message.get('message_id')
        if isinstance(message_id, str):
            # guard against bug-let in vumi messages that causes
            # message ids to be bytestrings when they're first
            # created but unicode after being de-serialized from
            # the wire.
            message_id = message_id.decode('ascii')
        opt_out = self.opt_outs(opt_out_id,
                user_account=self.user_account_key,
                message=message_id)
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

    def count(self):
        return self.opt_outs.index_lookup(
            'user_account', self.user_account_key).get_count()
