from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.vumitools.account.models import AccountStore
from go.vumitools.contact.models import ContactStore as ContactStoreV2
from go.vumitools.contact.old_models import ContactStoreVNone, ContactStoreV1


class TestContact(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = self.add_helper(
            PersistenceHelper(use_riak=True))
        riak_manager = self.persistence_helper.get_riak_manager()
        self.account_store = AccountStore(riak_manager)
        self.user = yield self.account_store.new_user(u'testuser')

        # Some old stores for testing migrations.
        self.contact_store_vnone = ContactStoreVNone(
            riak_manager, self.user.key)
        self.contact_store_v1 = ContactStoreV1(
            riak_manager, self.user.key)
        self.contact_store_v2 = ContactStoreV2(
            riak_manager, self.user.key)

    def assert_index(self, model_obj, index_name, *index_values):
        values = []
        for index in model_obj._riak_object.get_indexes():
            if index.get_field() == index_name:
                values.append(index.get_value())
        self.assertEqual(
            sorted(index_values), sorted(values),
            "Index value mismatch for %r: Expected %s, got %s" % (
                index_name, sorted(index_values), sorted(values)))

    @inlineCallbacks
    def test_contact_vnone(self):
        contact = yield self.contact_store_vnone.new_contact(
            name=u'name', msisdn=u'msisdn')
        self.assertEqual(contact.name, 'name')
        self.assertEqual(contact.msisdn, 'msisdn')

    @inlineCallbacks
    def test_contact_vnone_to_v1(self):
        contact_vnone = yield self.contact_store_vnone.new_contact(
            name=u'name', msisdn=u'msisdn')
        contact_vnone.extra["thing"] = u"extra-thing"
        contact_vnone.subscription["app"] = u"1"
        yield contact_vnone.save()
        self.assertEqual(contact_vnone.VERSION, None)
        contact_v1 = yield self.contact_store_v1.get_contact_by_key(
            contact_vnone.key)
        self.assertEqual(contact_v1.name, 'name')
        self.assertEqual(contact_v1.msisdn, 'msisdn')
        self.assertEqual(contact_v1.mxit_id, None)
        self.assertEqual(contact_v1.wechat_id, None)
        self.assertEqual(contact_v1.extra["thing"], u"extra-thing")
        self.assertEqual(contact_v1.subscription["app"], u"1")
        self.assertEqual(contact_v1.VERSION, 1)

    @inlineCallbacks
    def test_contact_v1_to_v2(self):
        contact_v1 = yield self.contact_store_v1.new_contact(
            name=u'name', msisdn=u'msisdn', mxit_id=u'mxit',
            wechat_id=u'wechat')
        contact_v1.extra["thing"] = u"extra-thing"
        contact_v1.subscription["app"] = u"1"
        yield contact_v1.save()
        self.assertEqual(contact_v1.VERSION, 1)
        contact_v2 = yield self.contact_store_v2.get_contact_by_key(
            contact_v1.key)
        self.assertEqual(contact_v2.name, 'name')
        self.assertEqual(contact_v2.msisdn, 'msisdn')
        self.assertEqual(contact_v2.mxit_id, 'mxit')
        self.assertEqual(contact_v2.wechat_id, 'wechat')
        self.assertEqual(contact_v2.extra["thing"], u"extra-thing")
        self.assertEqual(contact_v2.subscription["app"], u"1")
        self.assertEqual(contact_v2.VERSION, 2)
        self.assert_index(contact_v2, 'msisdn_bin', 'msisdn')

    @inlineCallbacks
    def test_contact_vnone_to_v2(self):
        contact_vnone = yield self.contact_store_vnone.new_contact(
            name=u'name', msisdn=u'msisdn')
        contact_vnone.extra["thing"] = u"extra-thing"
        contact_vnone.subscription["app"] = u"1"
        yield contact_vnone.save()
        self.assertEqual(contact_vnone.VERSION, None)
        contact_v2 = yield self.contact_store_v2.get_contact_by_key(
            contact_vnone.key)
        self.assertEqual(contact_v2.name, 'name')
        self.assertEqual(contact_v2.msisdn, 'msisdn')
        self.assertEqual(contact_v2.mxit_id, None)
        self.assertEqual(contact_v2.wechat_id, None)
        self.assertEqual(contact_v2.extra["thing"], u"extra-thing")
        self.assertEqual(contact_v2.subscription["app"], u"1")
        self.assertEqual(contact_v2.VERSION, 2)
        self.assert_index(contact_v2, 'msisdn_bin', 'msisdn')

    @inlineCallbacks
    def test_contact_v1(self):
        contact = yield self.contact_store_v1.new_contact(
            msisdn=u'msisdn', mxit_id=u'mxit', wechat_id=u'wechat')
        self.assertEqual(contact.msisdn, 'msisdn')
        self.assertEqual(contact.mxit_id, 'mxit')
        self.assertEqual(contact.wechat_id, 'wechat')

    @inlineCallbacks
    def test_contact_v2(self):
        contact = yield self.contact_store_v2.new_contact(
            msisdn=u'msisdn', mxit_id=u'mxit', wechat_id=u'wechat')
        self.assertEqual(contact.msisdn, 'msisdn')
        self.assertEqual(contact.mxit_id, 'mxit')
        self.assertEqual(contact.wechat_id, 'wechat')
        self.assert_index(contact, 'msisdn_bin', 'msisdn')
        self.assert_index(contact, 'mxit_id_bin', 'mxit')
        self.assert_index(contact, 'wechat_id_bin', 'wechat')
