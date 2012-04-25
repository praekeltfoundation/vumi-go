# -*- coding: utf-8 -*-

"""Tests for go.vumitools.contact."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from vumi.persist.txriak_manager import TxRiakManager

from go.vumitools.contact import ContactStore


class TestContactStore(TestCase):

    @inlineCallbacks
    def setUp(self):
        self.manager = TxRiakManager.from_config({'bucket_prefix': 'test.'})
        yield self.manager.purge_all()
        self.store = ContactStore(self.manager, u'user')
        self.store_alt = ContactStore(self.manager, u'other_user')

    def tearDown(self):
        return self.manager.purge_all()

    def model_eq(self, m1, m2):
        fields = m1.field_descriptors.keys()
        if fields != m2.field_descriptors.keys():
            return False
        if m1.key != m2.key:
            return False
        for field in fields:
            if getattr(m1, field) != getattr(m2, field):
                return False
        return True

    def assert_models_equal(self, m1, m2):
        self.assertTrue(self.model_eq(m1, m2),
                        "Models not equal:\na = %r\nb=%r" % (m1, m2))

    def assert_models_not_equal(self, m1, m2):
        self.assertFalse(self.model_eq(m1, m2),
                        "Models unexpectedly equal:\na = %r\nb=%r" % (m1, m2))

    @inlineCallbacks
    def test_new_group(self):
        self.assertEqual(None, (yield self.store.get_group(u'group1')))

        group = yield self.store.new_group(u'group1')
        self.assertEqual(u'group1', group.key)
        self.assertEqual(u'user', group.user)

        dbgroup = yield self.store.get_group(u'group1')
        self.assertEqual(u'group1', dbgroup.key)

        self.assert_models_equal(group, dbgroup)

    @inlineCallbacks
    def test_user_groups(self):
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
