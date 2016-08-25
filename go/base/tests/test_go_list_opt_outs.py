# -*- coding: utf-8 -*-
from StringIO import StringIO

from go.vumitools.tests.helpers import djangotest_imports
from go.vumitools.opt_out import OptOutStore

with djangotest_imports(globals()):
    from go.base.management.commands import go_list_accounts
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoListOptOutsCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        user_account = self.user_helper.get_user_account()
        user_account.can_manage_optouts = True
        user_account.save()
        self.optout_store = OptOutStore.from_user_account(user_account)

        self.contact_store = self.user_helper.user_api.contact_store
        self.contact = self.contact_store.new_contact(
            name='A', surname='Person', msisdn='+27123456789')

        self.msg = self.msg_helper.make_inbound('foo')
        self.optout_store.new_opt_out(
            'msisdn', self.contact.msisdn, self.msg)

        self.command = go_list_accounts.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_opt_out_listing(self):
        self.command.handle(**{
            'email-address': 'user@domain.com'
        })
        self.assertEqual(self.command.stdout.getvalue(), '\n'.join([
            "Address Type, Address, Message ID, Timestamp",
            "============================================",
            "msisdn,%s,%s,%s" % (self.contact.msisdn,
                                 self.msg.key,
                                 self.msg.timestamp)
        ]))
