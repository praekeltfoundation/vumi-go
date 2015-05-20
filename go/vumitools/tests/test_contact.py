# -*- coding: utf-8 -*-

"""Tests for go.vumitools.contact."""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.tests.utils import model_eq
from go.vumitools.contact import (
    ContactStore, ContactError, ContactNotFoundError)
from go.vumitools.opt_out import OptOutStore
from go.vumitools.tests.helpers import VumiApiHelper


class TestContactStore(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())

        self.user_helper = yield self.vumi_helper.make_user(u'user')
        user_account = yield self.user_helper.get_user_account()
        self.store = ContactStore.from_user_account(user_account)

        self.alt_user_helper = yield self.vumi_helper.make_user(u'other_user')
        alt_user_account = yield self.alt_user_helper.get_user_account()
        self.store_alt = ContactStore.from_user_account(alt_user_account)

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
            self.store.get_contact_by_key(u'123'), ContactNotFoundError)

    @inlineCallbacks
    def test_new_group(self):
        self.assertEqual(None, (yield self.store.get_group(u'group1')))

        group = yield self.store.new_group(u'group1')
        self.assertEqual(u'group1', group.name)

        dbgroup = yield self.store.get_group(group.key)
        self.assertEqual(u'group1', dbgroup.name)

        self.assert_models_equal(group, dbgroup)

    @inlineCallbacks
    def test_list_groups(self):
        self.assertEqual([], (yield self.store.list_groups()))

        group1 = yield self.store.new_group(u'group1')
        group2 = yield self.store.new_group(u'group2')
        sgroup1 = yield self.store.new_smart_group(u'sgroup1', u'surname:"a"')
        sgroup2 = yield self.store.new_smart_group(u'sgroup2', u'surname:"a"')

        [g1, g2, sg1, sg2] = yield self.store.list_groups()

        self.assert_models_equal(group1, g1)
        self.assert_models_equal(group2, g2)
        self.assert_models_equal(sgroup1, sg1)
        self.assert_models_equal(sgroup2, sg2)

    @inlineCallbacks
    def test_list_smart_groups(self):
        self.assertEqual([], (yield self.store.list_smart_groups()))

        yield self.store.new_group(u'group1')
        yield self.store.new_group(u'group2')
        sgroup1 = yield self.store.new_smart_group(u'sgroup1', u'surname:"a"')
        sgroup2 = yield self.store.new_smart_group(u'sgroup2', u'surname:"a"')

        [sg1, sg2] = yield self.store.list_smart_groups()

        self.assert_models_equal(sgroup1, sg1)
        self.assert_models_equal(sgroup2, sg2)

    @inlineCallbacks
    def test_list_static_groups(self):
        self.assertEqual([], (yield self.store.list_static_groups()))

        group1 = yield self.store.new_group(u'group1')
        group2 = yield self.store.new_group(u'group2')
        yield self.store.new_smart_group(u'sgroup1', u'surname:"a"')
        yield self.store.new_smart_group(u'sgroup2', u'surname:"a"')

        [g1, g2] = yield self.store.list_static_groups()

        self.assert_models_equal(group1, g1)
        self.assert_models_equal(group2, g2)

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
        contact.add_to_group(u'group-a')
        contact.add_to_group(u'group-b')
        yield contact.save()

        updated_contact = yield self.store.update_contact(
            contact.key, surname=u'Jackal', groups=['group-a', u'group-c'])
        dbcontact = yield self.store.get_contact_by_key(contact.key)

        self.assertEqual(u'J Random', updated_contact.name)
        self.assertEqual(u'Jackal', updated_contact.surname)
        self.assertEqual(u'27831234567', updated_contact.msisdn)
        self.assertEqual([u'group-a', u'group-b', u'group-c'],
                         updated_contact.groups.keys())
        self.assert_models_equal(dbcontact, updated_contact)

    def test_update_contact_for_nonexistent_contact(self):
        return self.assertFailure(
            self.store.update_contact('123124'), ContactNotFoundError)

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

        contact_keys_page_g1 = yield group1.backlinks.contact_keys()
        contact_keys_page_g2 = yield group2.backlinks.contact_keys()
        self.assertEqual([contact.key], list(contact_keys_page_g1))
        self.assertEqual([contact.key], list(contact_keys_page_g2))

    @inlineCallbacks
    def test_check_for_opted_out_contact(self):
        contact1 = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')
        contact2 = yield self.store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27830000000')

        # Opt out the first contact
        user_account = yield self.user_helper.get_user_account()
        optout_store = OptOutStore.from_user_account(user_account)
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
        group = yield self.store.new_smart_group(u'test group',
                                                 u'surname:"Foo 1"')
        for i in range(2):
            yield self.store.new_contact(
                name=u'Contact', surname=u'Foo %d' % i, msisdn=u'12345')
        count = yield self.store.count_contacts_for_group(group)
        self.assertEqual(count, 1)

    @inlineCallbacks
    def test_new_contact_for_addr(self):
        @inlineCallbacks
        def check_new_contact_for_addr(deliv_class, addr, **kw):
            contact = yield self.store.new_contact_for_addr(deliv_class, addr)
            self.assertEqual(
                contact.user_account.key, self.user_helper.account_key)
            for field, expected_value in kw.iteritems():
                self.assertEqual(getattr(contact, field), expected_value)

        yield check_new_contact_for_addr('sms', u'+27831234567',
                                         msisdn=u'+27831234567')
        yield check_new_contact_for_addr('ussd', u'+27831234567',
                                         msisdn=u'+27831234567')
        yield check_new_contact_for_addr('gtalk', u'random@gmail.com',
                                         gtalk_id=u'random@gmail.com',
                                         msisdn=u'unknown')
        yield check_new_contact_for_addr('twitter', u'random',
                                         twitter_handle=u'random',
                                         msisdn=u'unknown')
        yield check_new_contact_for_addr('mxit', u'mxit',
                                         mxit_id=u'mxit',
                                         msisdn=u'unknown')
        yield check_new_contact_for_addr('wechat', u'wechat',
                                         wechat_id=u'wechat',
                                         msisdn=u'unknown')

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
            twitter_handle=u'random',
            mxit_id=u'mxit',
            wechat_id=u'wechat')

        yield check_contact_for_addr('sms', u'+27831234567', contact)
        yield check_contact_for_addr('ussd', u'+27831234567', contact)
        yield check_contact_for_addr('gtalk', u'random@gmail.com', contact)
        yield check_contact_for_addr('twitter', u'random', contact)
        yield check_contact_for_addr('mxit', u'mxit', contact)
        yield check_contact_for_addr('wechat', u'wechat', contact)
        yield check_contact_for_addr('voice', u'+27831234567', contact)

    def test_contact_for_addr_for_unsupported_transports(self):
        return self.assertFailure(
            self.store.contact_for_addr('bad_transport_type', u'234234'),
            ContactError)

    def test_contact_for_addr_for_nonexistent_contacts(self):
        return self.assertFailure(
            self.store.contact_for_addr('sms', u'27831234567', create=False),
            ContactNotFoundError)

    @inlineCallbacks
    def test_contact_for_addr_for_contact_creation(self):
        @inlineCallbacks
        def check_contact_for_addr(deliv_class, addr, **kw):
            contact = yield self.store.contact_for_addr(deliv_class, addr)
            self.assertEqual(
                contact.user_account.key, self.user_helper.account_key)
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
        yield check_contact_for_addr('mxit', u'mxit',
                                     mxit_id=u'mxit',
                                     msisdn=u'unknown')
        yield check_contact_for_addr('wechat', u'wechat',
                                     wechat_id=u'wechat',
                                     msisdn=u'unknown')
        yield check_contact_for_addr('voice', u'+27831234567',
                                     msisdn=u'+27831234567')
