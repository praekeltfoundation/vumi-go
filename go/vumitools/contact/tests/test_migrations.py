from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.vumitools.account.models import AccountStore
from go.vumitools.contact.old_models import (
    ContactStoreVNone, ContactStoreV1)


class TestContact(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = self.add_helper(
            PersistenceHelper(use_riak=True))
        riak_manager = self.persistence_helper.get_riak_manager()
        self.account_store = AccountStore(riak_manager)
        self.user = yield self.account_store.new_user(u'testuser')

        # Some old stores for testing migrations.
        self.contacts_store_vnone = ContactStoreVNone(
            riak_manager, self.user.key)
        # Some old stores for testing migrations.
        self.contacts_store_v1 = ContactStoreV1(
            riak_manager, self.user.key)

    @inlineCallbacks
    def test_contact_vnone(self):
        contact = yield self.contacts_store_vnone.new_contact(
            name=u'name', msisdn=u'msisdn')
        self.assertEqual(contact.name, 'name')
        self.assertEqual(contact.msisdn, 'msisdn')

    @inlineCallbacks
    def test_contact_vnone_to_v1(self):
        contact_vnone = yield self.contacts_store_vnone.new_contact(
            name=u'name', msisdn=u'msisdn')
        contact_v1 = yield self.contacts_store_v1.get_contact_by_key(
            contact_vnone.key)
        self.assertEqual(contact_v1.name, 'name')
        self.assertEqual(contact_v1.msisdn, 'msisdn')
        self.assertEqual(contact_v1.mxit_id, None)
        self.assertEqual(contact_v1.wechat_id, None)

    @inlineCallbacks
    def test_contact_v1(self):
        contact = yield self.contacts_store_v1.new_contact(
            msisdn=u'msisdn', mxit_id=u'mxit', wechat_id=u'wechat')
        self.assertEqual(contact.msisdn, 'msisdn')
        self.assertEqual(contact.mxit_id, 'mxit')
        self.assertEqual(contact.wechat_id, 'wechat')
