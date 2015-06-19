from optparse import make_option

from go.base.command_utils import BaseGoCommand, make_email_option
from go.vumitools.opt_out import OptOutStore


class Command(BaseGoCommand):
    help = "List opt-outs from a particular account"

    LOCAL_OPTIONS = [
        make_email_option()
    ]

    option_list = BaseGoCommand.option_list + tuple(LOCAL_OPTIONS)

    def handle(self, *args, **options):
        options = options.copy()
        self.handle_validated(*args, **options)

    def handle_validated(self, *args, **options):
        _, user_api = self.mk_user_api(options['email-address'])

        self.show_opt_outs(user_api, email_address)

    def show_opt_outs(self, user_api, email_address):
        opt_out_store = OptOutStore(user_api.manager,
                                    user_api.user_account_key)
        opt_outs = opt_out_store.list_opt_outs()

        print "Address Type, Address, Message ID, Timestamp"
        print "============================================"
        for key in opt_outs:
            addr_type, _colon, addr = key.partition(":")
            opt_out = opt_out_store.get_opt_out(addr_type, addr)
            print "%s, %s, %s, %s" % (addr_type, addr, opt_out.message,
                                      opt_out.created_at)
