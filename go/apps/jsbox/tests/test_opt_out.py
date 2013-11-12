# -*- coding: utf-8 -*-

from mock import Mock

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.opt_out import OptOutResource
from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.account import AccountStore
from go.vumitools.contact import ContactStore
from go.vumitools.opt_out import OptOutStore
from go.vumitools.tests.helpers import GoMessageHelper


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.user_api = Mock()

    def user_api_for_api(self, api):
        return self.user_api


class OptOutResourceTestCase(ResourceTestCaseBase, GoPersistenceMixin):
    use_riak = True
    app_worker_cls = StubbedAppWorker
    resource_cls = OptOutResource

    @inlineCallbacks
    def setUp(self):
        super(OptOutResourceTestCase, self).setUp()
        yield self._persist_setUp()

        self.msg_helper = GoMessageHelper()

        # We pass `self` in as the VumiApi object here, because mk_user() just
        # grabs .account_store off it.
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        self.account = yield self.mk_user(self, u'user')
        self.account.can_manage_optouts = True
        self.contact_store = ContactStore.from_user_account(self.account)
        self.optout_store = OptOutStore.from_user_account(self.account)
        yield self.contact_store.contacts.enable_search()

        yield self.create_resource({})

        self.user_api = self.app_worker.user_api
        self.user_api.contact_store = self.contact_store
        self.user_api.optout_store = self.optout_store
        self.user_api.get_user_account = Mock(
            return_value=succeed(self.account))

        self.contact1 = yield self.new_contact(
            name=u'A',
            surname=u'Person',
            msisdn=u'+27123456789')

        self.contact2 = yield self.new_contact(
            name=u'B',
            surname=u'Person',
            msisdn=u'+27000000000')

    def tearDown(self):
        super(OptOutResourceTestCase, self).tearDown()
        return self._persist_tearDown()

    def optout(self, msisdn):
        return self.optout_store.new_opt_out(
            'msisdn', msisdn, self.msg_helper.make_inbound('foo'))

    @inlineCallbacks
    def new_contact(self, **fields):
        groups = fields.pop('groups', [])
        contact = yield self.contact_store.new_contact(**fields)
        for group in groups:
            contact.add_to_group(group)
        yield contact.save()
        returnValue(contact)

    @inlineCallbacks
    def test_handle_status_optedout(self):
        yield self.optout(self.contact1.msisdn)
        reply = yield self.dispatch_command(
            'status',
            address_type=u'msisdn',
            address_value=self.contact1.msisdn)

        self.assertTrue(reply['success'])
        self.assertTrue(reply['opted_out'])

    @inlineCallbacks
    def test_handle_status_optedin(self):
        reply = yield self.dispatch_command(
            'status',
            address_type=u'msisdn',
            address_value=self.contact1.msisdn)

        self.assertTrue(reply['success'])
        self.assertFalse(reply['opted_out'])

    @inlineCallbacks
    def test_ensure_params_missing_key(self):
        reply = yield self.dispatch_command('status')
        self.assertFalse(reply['success'])
        self.assertEqual(reply['reason'],
                         'Missing key: address_type')

    @inlineCallbacks
    def test_ensure_params_invalid_value(self):
        reply = yield self.dispatch_command('status', address_type=None)
        self.assertFalse(reply['success'])
        self.assertEqual(reply['reason'],
                         'Invalid value "None" for "address_type"')

    @inlineCallbacks
    def test_handle_count(self):
        def assert_count(count):
            reply = yield self.dispatch_command('count')
            self.assertTrue(reply['success'])
            self.assertEqual(reply['count'], count)

        yield assert_count(0)
        yield self.optout(self.contact1.msisdn)
        yield assert_count(1)

    @inlineCallbacks
    def test_handle_optout(self):
        msg = self.msg_helper.make_inbound('stop')
        reply = yield self.dispatch_command(
            'optout',
            address_type='msisdn',
            address_value=self.contact1.msisdn,
            message_id=msg['message_id'])
        self.assertTrue(reply['success'])
        self.assertTrue(reply['opted_out'])
        self.assertEqual(reply['message_id'], msg['message_id'])

    @inlineCallbacks
    def test_handle_cancel_optout(self):
        yield self.optout(self.contact1.msisdn)
        reply = yield self.dispatch_command(
            'cancel_optout',
            address_type='msisdn',
            address_value=self.contact1.msisdn)
        self.assertTrue(reply['success'])
        self.assertFalse(reply['opted_out'])

    @inlineCallbacks
    def test_account_can_manage_optouts(self):
        self.account.can_manage_optouts = False
        reply = yield self.dispatch_command('count')
        self.assertFalse(reply['success'])
        self.assertEqual(
            reply['reason'],
            'Account not allowed to manage optouts.')
