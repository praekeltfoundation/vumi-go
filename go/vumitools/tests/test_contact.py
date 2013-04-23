# -*- coding: utf-8 -*-

"""Tests for go.vumitools.contact."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from go.vumitools.tests.utils import model_eq, GoPersistenceMixin
from go.vumitools.account import AccountStore
from go.vumitools.contact import ContactStore, ContactError
from go.vumitools.opt_out import OptOutStore


class TestContactStore(GoPersistenceMixin, TestCase):
    use_riak = True

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        # We pass `self` in as the VumiApi object here, because mk_user() just
        # grabs .account_store off it.
        self.account = yield self.mk_user(self, u'user')
        self.account_alt = yield self.mk_user(self, u'other_user')
        self.store = ContactStore.from_user_account(self.account)
        self.store_alt = ContactStore.from_user_account(self.account_alt)

    def tearDown(self):
        return self._persist_tearDown()

    def assert_models_equal(self, m1, m2):
        self.assertTrue(model_eq(m1, m2),
                        "Models not equal:\na: %r\nb: %r" % (m1, m2))

    def assert_models_not_equal(self, m1, m2):
        self.assertFalse(model_eq(m1, m2),
                         "Models unexpectedly equal:\na: %r\nb: %r" % (m1, m2))

    @inlineCallbacks
    def test_get_contact_by_key(self):
        contact = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')
        self.assert_models_equal(
            contact, (yield self.store.get_contact_by_key(contact.key)))

    def test_get_contact_by_key_for_nonexistent_contact(self):
        return self.assertFailure(
            self.store.get_contact_by_key(u'123'), ContactError)

    @inlineCallbacks
    def test_new_group(self):
        self.assertEqual(None, (yield self.store.get_group(u'group1')))

        group = yield self.store.new_group(u'group1')
        self.assertEqual(u'group1', group.name)

        dbgroup = yield self.store.get_group(group.key)
        self.assertEqual(u'group1', dbgroup.name)

        self.assert_models_equal(group, dbgroup)

    # TODO: Either implement unique group names or delete this test.
    # @inlineCallbacks
    # def test_new_group_exists(self):
    #     self.assertEqual(None, (yield self.store.get_group(u'group1')))

    #     group = yield self.store.new_group(u'group1')
    #     self.assertEqual(u'group1', group.name)

    #     try:
    #         yield self.store.new_group(u'group1')
    #         self.fail("Expected ValueError.")
    #     except ValueError:
    #         pass

    #     dbgroup = yield self.store.get_group(u'group1')
    #     self.assert_models_equal(group, dbgroup)

    @inlineCallbacks
    def test_per_user_groups(self):
        group = yield self.store.new_group(u'group1')
        dbgroup = yield self.store.get_group(group.key)
        self.assertNotEqual(None, dbgroup)
        self.assertEqual(None, (yield self.store_alt.get_group(group.key)))

        group_alt = yield self.store_alt.new_group(u'group1')
        dbgroup_alt = yield self.store_alt.get_group(group_alt.key)
        self.assert_models_equal(group, dbgroup)
        self.assert_models_equal(group_alt, dbgroup_alt)
        self.assert_models_not_equal(group, group_alt)

    @inlineCallbacks
    def test_new_contact(self):
        contact = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')
        self.assertEqual(u'J Random', contact.name)
        self.assertEqual(u'Person', contact.surname)
        self.assertEqual(u'27831234567', contact.msisdn)

        dbcontact = yield self.store.get_contact_by_key(contact.key)

        self.assert_models_equal(contact, dbcontact)

    @inlineCallbacks
    def test_update_contact(self):
        contact = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')

        updated_contact = yield self.store.update_contact(contact.key,
                                                          surname=u'Jackal')
        dbcontact = yield self.store.get_contact_by_key(contact.key)

        self.assertEqual(u'J Random', updated_contact.name)
        self.assertEqual(u'Jackal', updated_contact.surname)
        self.assertEqual(u'27831234567', updated_contact.msisdn)
        self.assert_models_equal(dbcontact, updated_contact)

    def test_update_contact_for_nonexistent_contact(self):
        return self.assertFailure(
            self.store.update_contact('123124'), ContactError)

    @inlineCallbacks
    def test_save_contact(self):
        contact = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')

        yield self.store.save_contact(
            contact.key, surname=u'Robot', msisdn=u'unknown')

        dbcontact = yield self.store.get_contact_by_key(contact.key)
        self.assertEqual(None, dbcontact.name)
        self.assertEqual(u'Robot', dbcontact.surname)
        self.assertEqual(u'unknown', dbcontact.msisdn)

    @inlineCallbacks
    def test_add_contact_to_group(self):
        contact = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')
        group1 = yield self.store.new_group(u'group1')
        group2 = yield self.store.new_group(u'group2')

        self.assertEqual([], contact.groups.keys())
        contact.add_to_group(group1)
        self.assertEqual([group1.key], contact.groups.keys())
        contact.add_to_group(group2.key)
        self.assertEqual([group1.key, group2.key], contact.groups.keys())

        yield contact.save()
        dbcontact = yield self.store.get_contact_by_key(contact.key)
        self.assert_models_equal(contact, dbcontact)

        group1 = yield self.store.get_group(group1.key)
        group2 = yield self.store.get_group(group2.key)

        self.assertEqual([contact.key], (yield group1.backlinks.contacts()))
        self.assertEqual([contact.key], (yield group2.backlinks.contacts()))

    @inlineCallbacks
    def test_check_for_opted_out_contact(self):
        contact1 = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')
        contact2 = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27830000000')

        # Opt out the first contact
        optout_store = OptOutStore.from_user_account(self.account)
        yield optout_store.new_opt_out(u'msisdn', contact1.msisdn, {
            'message_id': u'the-message-id'
        })

        self.assertTrue((yield self.store.contact_has_opted_out(contact1)))
        self.assertFalse((yield self.store.contact_has_opted_out(contact2)))

    @inlineCallbacks
    def test_count_contacts_for_static_group(self):
        group = yield self.store.new_group(u'test group')
        for i in range(2):
            yield self.store.new_contact(
                name=u'Contact', surname=u'%d' % i, msisdn=u'12345',
                groups=[group])
        count = yield self.store.count_contacts_for_group(group)
        self.assertEqual(count, 2)

    @inlineCallbacks
    def test_count_contacts_for_smart_group(self):
        yield self.store.contacts.enable_search()
        group = yield self.store.new_smart_group(u'test group',
                                                 u'surname:"Foo 1"')
        for i in range(2):
            yield self.store.new_contact(
                name=u'Contact', surname=u'Foo %d' % i, msisdn=u'12345')
        count = yield self.store.count_contacts_for_group(group)
        self.assertEqual(count, 1)

    @inlineCallbacks
    def test_contact_for_addr(self):
        @inlineCallbacks
        def check_contact_for_addr(delivery_class, addr, expected_contact):
            contact = yield self.store.contact_for_addr(delivery_class, addr)
            self.assert_models_equal(expected_contact, contact)

        contact = yield self.store.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567',
            gtalk_id=u'random@gmail.com',
            twitter_handle=u'random')

        yield check_contact_for_addr('sms', u'+27831234567', contact)
        yield check_contact_for_addr('ussd', u'+27831234567', contact)
        yield check_contact_for_addr('gtalk', u'random@gmail.com', contact)
        yield check_contact_for_addr('twitter', u'random', contact)

    def test_contact_for_addr_for_unsupported_transports(self):
        return self.assertFailure(
            self.store.contact_for_addr('bad_transport_type', u'234234'),
            ContactError)

    def test_contact_for_addr_for_nonexistent_contacts(self):
        return self.assertFailure(
            self.store.contact_for_addr('sms', u'27831234567', create=False),
            ContactError)

    @inlineCallbacks
    def test_contact_for_addr_for_contact_creation(self):
        @inlineCallbacks
        def check_contact_for_addr(deliv_class, addr, **kw):
            contact = yield self.store.contact_for_addr(
                deliv_class, addr)
            self.assertEqual(contact.user_account.key, self.account.key)
            for field, expected_value in kw.iteritems():
                self.assertEqual(getattr(contact, field), expected_value)

        yield check_contact_for_addr('sms', u'+27831234567',
                                     msisdn=u'+27831234567')
        yield check_contact_for_addr('ussd', u'+27831234567',
                                     msisdn=u'+27831234567')
        yield check_contact_for_addr('gtalk', u'random@gmail.com',
                                     gtalk_id=u'random@gmail.com',
                                     msisdn=u'unknown')
        yield check_contact_for_addr('twitter', u'random',
                                     twitter_handle=u'random',
                                     msisdn=u'unknown')
