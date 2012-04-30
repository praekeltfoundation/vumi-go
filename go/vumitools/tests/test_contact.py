# -*- coding: utf-8 -*-

"""Tests for go.vumitools.contact."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from vumi.persist.txriak_manager import TxRiakManager

from go.vumitools.tests.utils import model_eq
from go.vumitools.account import AccountStore
from go.vumitools.contact import ContactStore


class TestContactStore(TestCase):

    @inlineCallbacks
    def setUp(self):
        self.manager = TxRiakManager.from_config({'bucket_prefix': 'test.'})
        yield self.manager.purge_all()
        self.account_store = AccountStore(self.manager)
        account = yield self.account_store.new_user(u'user')
        account_alt = yield self.account_store.new_user(u'other_user')
        self.store = ContactStore.from_user_account(account)
        self.store_alt = ContactStore.from_user_account(account_alt)

    def tearDown(self):
        return self.manager.purge_all()

    def assert_models_equal(self, m1, m2):
        self.assertTrue(model_eq(m1, m2),
                        "Models not equal:\na: %r\nb: %r" % (m1, m2))

    def assert_models_not_equal(self, m1, m2):
        self.assertFalse(model_eq(m1, m2),
                         "Models unexpectedly equal:\na: %r\nb: %r" % (m1, m2))

    @inlineCallbacks
    def test_new_group(self):
        self.assertEqual(None, (yield self.store.get_group(u'group1')))

        group = yield self.store.new_group(u'group1')
        self.assertEqual(u'group1', group.key)

        dbgroup = yield self.store.get_group(u'group1')
        self.assertEqual(u'group1', dbgroup.key)

        self.assert_models_equal(group, dbgroup)

    @inlineCallbacks
    def test_new_group_exists(self):
        self.assertEqual(None, (yield self.store.get_group(u'group1')))

        group = yield self.store.new_group(u'group1')
        self.assertEqual(u'group1', group.key)

        try:
            yield self.store.new_group(u'group1')
            self.fail("Expected ValueError.")
        except ValueError:
            pass

        dbgroup = yield self.store.get_group(u'group1')
        self.assert_models_equal(group, dbgroup)

    @inlineCallbacks
    def test_per_user_groups(self):
        self.assertEqual(None, (yield self.store.get_group(u'group1')))
        self.assertEqual(None, (yield self.store_alt.get_group(u'group1')))
        group = yield self.store.new_group(u'group1')

        self.assertNotEqual(None, (yield self.store.get_group(u'group1')))
        self.assertEqual(None, (yield self.store_alt.get_group(u'group1')))
        group_alt = yield self.store_alt.new_group(u'group1')

        dbgroup = yield self.store.get_group(u'group1')
        dbgroup_alt = yield self.store_alt.get_group(u'group1')
        self.assert_models_equal(group, dbgroup)
        self.assert_models_equal(group_alt, dbgroup_alt)
        self.assert_models_not_equal(group, group_alt)

    @inlineCallbacks
    def test_new_contact(self):
        contact = yield self.store.new_contact(
            u'J Random', u'Person', msisdn=u'27831234567')
        self.assertEqual(u'J Random', contact.name)
        self.assertEqual(u'Person', contact.surname)
        self.assertEqual(u'27831234567', contact.msisdn)

        dbcontact = yield self.store.get_contact_by_key(contact.key)

        self.assert_models_equal(contact, dbcontact)

    @inlineCallbacks
    def test_add_contact_to_group(self):
        contact = yield self.store.new_contact(
            u'J Random', u'Person', msisdn=u'27831234567')
        group1 = yield self.store.new_group(u'group1')
        group2 = yield self.store.new_group(u'group2')

        self.assertEqual([], contact.groups.keys())
        contact.add_to_group(group1)
        self.assertEqual([u'group1'], contact.groups.keys())
        contact.add_to_group(group2.key)
        self.assertEqual([u'group1', u'group2'], contact.groups.keys())

        yield contact.save()
        dbcontact = yield self.store.get_contact_by_key(contact.key)
        self.assert_models_equal(contact, dbcontact)

        group1 = yield self.store.get_group(u'group1')
        group2 = yield self.store.get_group(u'group2')

        self.assertEqual([contact.key],
                         [c.key for c in (yield group1.backlinks.contacts())])

        self.assertEqual([contact.key],
                         [c.key for c in (yield group2.backlinks.contacts())])
