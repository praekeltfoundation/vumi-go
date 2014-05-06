from uuid import uuid4

from twisted.internet.defer import inlineCallbacks
from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.vumitools.account.models import AccountStore
from go.vumitools.contact.models import (
    ContactNotFoundError, Contact, ContactStore)
from go.vumitools.contact.old_models import ContactVNone, ContactV1
from go.vumitools.tests.helpers import VumiApiHelper


class TestContact(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = self.add_helper(
            PersistenceHelper(use_riak=True))
        riak_manager = self.persistence_helper.get_riak_manager()
        self.account_store = AccountStore(riak_manager)
        self.user = yield self.account_store.new_user(u'testuser')

        # Some old contact proxies for testing migrations.
        per_account_manager = riak_manager.sub_manager(self.user.key)
        self.contacts_vnone = per_account_manager.proxy(ContactVNone)
        self.contacts_v1 = per_account_manager.proxy(ContactV1)
        self.contacts_v2 = per_account_manager.proxy(Contact)

    def assert_with_index(self, model_obj, field, value):
        self.assertEqual(getattr(model_obj, field), value)
        index_name = '%s_bin' % (field,)
        index_values = []
        for index in model_obj._riak_object.get_indexes():
            if index.get_field() == index_name:
                index_values.append(index.get_value())
        if value is None:
            self.assertEqual([], index_values)
        else:
            self.assertEqual([value], index_values)

    def _make_contact(self, model_proxy, **fields):
        contact_id = uuid4().get_hex()
        groups = fields.pop('groups', [])
        contact = model_proxy(contact_id, user_account=self.user.key, **fields)
        for group in groups:
            contact.add_to_group(group)
        d = contact.save()
        d.addCallback(lambda _: contact)
        return d

    def make_contact_vnone(self, **fields):
        return self._make_contact(self.contacts_vnone, **fields)

    def make_contact_v1(self, **fields):
        return self._make_contact(self.contacts_v1, **fields)

    def make_contact_v2(self, **fields):
        return self._make_contact(self.contacts_v2, **fields)

    @inlineCallbacks
    def test_contact_vnone(self):
        contact = yield self.make_contact_vnone(name=u'name', msisdn=u'msisdn')
        self.assertEqual(contact.name, 'name')
        self.assertEqual(contact.msisdn, 'msisdn')

    @inlineCallbacks
    def test_contact_v1(self):
        contact = yield self.make_contact_v1(
            msisdn=u'msisdn', mxit_id=u'mxit', wechat_id=u'wechat')
        self.assertEqual(contact.msisdn, 'msisdn')
        self.assertEqual(contact.mxit_id, 'mxit')
        self.assertEqual(contact.wechat_id, 'wechat')

    @inlineCallbacks
    def test_contact_vnone_to_v1(self):
        contact_vnone = yield self.make_contact_vnone(
            name=u'name', msisdn=u'msisdn')
        contact_vnone.extra["thing"] = u"extra-thing"
        contact_vnone.subscription["app"] = u"1"
        yield contact_vnone.save()
        self.assertEqual(contact_vnone.VERSION, None)
        contact_v1 = yield self.contacts_v1.load(contact_vnone.key)
        self.assertEqual(contact_v1.name, 'name')
        self.assertEqual(contact_v1.msisdn, 'msisdn')
        self.assertEqual(contact_v1.mxit_id, None)
        self.assertEqual(contact_v1.wechat_id, None)
        self.assertEqual(contact_v1.extra["thing"], u"extra-thing")
        self.assertEqual(contact_v1.subscription["app"], u"1")
        self.assertEqual(contact_v1.VERSION, 1)

    @inlineCallbacks
    def test_contact_v2(self):
        contact = yield self.make_contact_v2(
            name=u'name', msisdn=u'msisdn', twitter_handle=u'twitter',
            facebook_id=u'facebook', bbm_pin=u'bbm', gtalk_id=u'gtalk',
            mxit_id=u'mxit', wechat_id=u'wechat')

        self.assertEqual(contact.name, 'name')
        self.assert_with_index(contact, 'msisdn', 'msisdn')
        self.assert_with_index(contact, 'twitter_handle', 'twitter')
        self.assert_with_index(contact, 'facebook_id', 'facebook')
        self.assert_with_index(contact, 'bbm_pin', 'bbm')
        self.assert_with_index(contact, 'gtalk_id', 'gtalk')
        self.assert_with_index(contact, 'mxit_id', 'mxit')
        self.assert_with_index(contact, 'wechat_id', 'wechat')

    @inlineCallbacks
    def test_contact_v1_to_v2(self):
        contact_v1 = yield self.make_contact_v1(
            name=u'name', msisdn=u'msisdn', twitter_handle=u'twitter',
            facebook_id=u'facebook', bbm_pin=u'bbm', gtalk_id=u'gtalk',
            mxit_id=u'mxit', wechat_id=u'wechat')
        contact_v1.extra["thing"] = u"extra-thing"
        contact_v1.subscription["app"] = u"1"
        yield contact_v1.save()
        self.assertEqual(contact_v1.VERSION, 1)
        contact_v2 = yield self.contacts_v2.load(contact_v1.key)
        self.assertEqual(contact_v2.name, 'name')
        self.assertEqual(contact_v2.extra["thing"], u"extra-thing")
        self.assertEqual(contact_v2.subscription["app"], u"1")
        self.assertEqual(contact_v2.VERSION, 2)
        self.assert_with_index(contact_v2, 'msisdn', 'msisdn')
        self.assert_with_index(contact_v2, 'twitter_handle', 'twitter')
        self.assert_with_index(contact_v2, 'facebook_id', 'facebook')
        self.assert_with_index(contact_v2, 'bbm_pin', 'bbm')
        self.assert_with_index(contact_v2, 'gtalk_id', 'gtalk')
        self.assert_with_index(contact_v2, 'mxit_id', 'mxit')
        self.assert_with_index(contact_v2, 'wechat_id', 'wechat')

    @inlineCallbacks
    def test_contact_vnone_to_v2(self):
        contact_vnone = yield self.make_contact_vnone(
            name=u'name', msisdn=u'msisdn', twitter_handle=u'twitter',
            facebook_id=u'facebook', bbm_pin=u'bbm', gtalk_id=u'gtalk')
        contact_vnone.extra["thing"] = u"extra-thing"
        contact_vnone.subscription["app"] = u"1"
        yield contact_vnone.save()
        self.assertEqual(contact_vnone.VERSION, None)
        contact_v2 = yield self.contacts_v2.load(contact_vnone.key)
        self.assertEqual(contact_v2.name, 'name')
        self.assertEqual(contact_v2.extra["thing"], u"extra-thing")
        self.assertEqual(contact_v2.subscription["app"], u"1")
        self.assertEqual(contact_v2.VERSION, 2)
        self.assert_with_index(contact_v2, 'msisdn', 'msisdn')
        self.assert_with_index(contact_v2, 'twitter_handle', 'twitter')
        self.assert_with_index(contact_v2, 'facebook_id', 'facebook')
        self.assert_with_index(contact_v2, 'bbm_pin', 'bbm')
        self.assert_with_index(contact_v2, 'gtalk_id', 'gtalk')
        self.assert_with_index(contact_v2, 'mxit_id', None)
        self.assert_with_index(contact_v2, 'wechat_id', None)


class TestContactStore(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.get_or_create_user()
        riak_manager = self.vumi_helper.get_riak_manager()
        self.contact_store = ContactStore(
            riak_manager, self.user_helper.account_key)
        # Old contact proxy for making unindexed contacts.
        per_account_manager = riak_manager.sub_manager(
            self.user_helper.account_key)
        self.contacts_v1 = per_account_manager.proxy(ContactV1)

    def make_unindexed_contact(self, **fields):
        contact_id = uuid4().get_hex()
        groups = fields.pop('groups', [])
        contact = self.contacts_v1(
            contact_id, user_account=self.user_helper.account_key, **fields)
        for group in groups:
            contact.add_to_group(group)
        d = contact.save()
        d.addCallback(lambda _: contact)
        return d

    @inlineCallbacks
    def test_contact_for_addr_not_found(self):
        yield self.contact_store.new_contact(
            name=u'name', msisdn=u'+27831234567')
        self.contact_store.FIND_BY_INDEX_SEARCH_FALLBACK = False
        contact_d = self.contact_store.contact_for_addr(
            'sms', u'nothing', create=False)
        yield self.assertFailure(contact_d, ContactNotFoundError)

    @inlineCallbacks
    def test_contact_for_addr_msisdn(self):
        contact = yield self.contact_store.new_contact(
            name=u'name', msisdn=u'+27831234567')
        found_contact = yield self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=False)
        self.assertEqual(contact.key, found_contact.key)

    @inlineCallbacks
    def test_contact_for_addr_gtalk(self):
        contact = yield self.contact_store.new_contact(
            name=u'name', msisdn=u'+27831234567', gtalk_id=u'foo@example.com')
        found_contact = yield self.contact_store.contact_for_addr(
            'gtalk', u'foo@example.com', create=False)
        self.assertEqual(contact.key, found_contact.key)

    @inlineCallbacks
    def test_contact_for_addr_unindexed(self):
        contact = yield self.make_unindexed_contact(
            name=u'name', msisdn=u'+27831234567')
        found_contact = yield self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=False)
        self.assertEqual(contact.key, found_contact.key)

    @inlineCallbacks
    def test_contact_for_addr_unindexed_index_disabled(self):
        contact = yield self.make_unindexed_contact(
            name=u'name', msisdn=u'+27831234567')
        self.contact_store.FIND_BY_INDEX = False
        found_contact = yield self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=False)
        self.assertEqual(contact.key, found_contact.key)

    @inlineCallbacks
    def test_contact_for_addr_unindexed_index_and_fallback_disabled(self):
        contact = yield self.make_unindexed_contact(
            name=u'name', msisdn=u'+27831234567')
        self.contact_store.FIND_BY_INDEX = False
        found_contact = yield self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=False)
        self.assertEqual(contact.key, found_contact.key)

    @inlineCallbacks
    def test_contact_for_addr_unindexed_fallback_disabled(self):
        yield self.make_unindexed_contact(name=u'name', msisdn=u'+27831234567')
        self.contact_store.FIND_BY_INDEX_SEARCH_FALLBACK = False
        contact_d = self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=False)
        yield self.assertFailure(contact_d, ContactNotFoundError)

    @inlineCallbacks
    def test_contact_for_addr_indexed_fallback_disabled(self):
        contact = yield self.contact_store.new_contact(
            name=u'name', msisdn=u'+27831234567')
        self.contact_store.FIND_BY_INDEX_SEARCH_FALLBACK = False
        found_contact = yield self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=False)
        self.assertEqual(contact.key, found_contact.key)

    @inlineCallbacks
    def test_contact_for_addr_new(self):
        contact = yield self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=True)
        self.assertEqual(contact.msisdn, u'+27831234567')

    @inlineCallbacks
    def test_new_contact_for_addr(self):
        contact = yield self.contact_store.new_contact_for_addr(
            'sms', u'+27831234567')
        self.assertEqual(contact.msisdn, u'+27831234567')

    @inlineCallbacks
    def test_new_contact_for_addr_gtalk(self):
        contact = yield self.contact_store.new_contact_for_addr(
            'gtalk', u'foo@example.com')
        self.assertEqual(contact.gtalk_id, u'foo@example.com')
        self.assertEqual(contact.msisdn, u'unknown')
