from optparse import make_option

from go.base.command_utils import BaseGoAccountCommand
from go.vumitools.opt_out import OptOutStore


class Command(BaseGoCommand):
    help = "List opt-outs from a particular account"

    def handle_no_command(self, *args, **options):
        options = options.copy()
        self.handle_validated(*args, **options)

    def handle_validated(self, *args, **options):
        self.show_opt_outs()

    def show_opt_outs(self):
        opt_out_store = OptOutStore(self.user_api.manager,
                                    self.user_api.user_account_key)
        opt_outs = opt_out_store.list_opt_outs()

        print "Address Type, Address, Message ID, Timestamp"
        print "============================================"
        for key in opt_outs:
            addr_type, _colon, addr = key.partition(":")
            opt_out = opt_out_store.get_opt_out(addr_type, addr)
            print "%s, %s, %s, %s" % (addr_type, addr, opt_out.message,
                                      opt_out.created_at)
