from uuid import uuid4

from twisted.internet.defer import inlineCallbacks, succeed
from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.vumitools.account.models import AccountStore
from go.vumitools.contact.models import (
    ContactNotFoundError, Contact, ContactStore, PaginatedSearch,
    ChainedIndexPages)
from go.vumitools.contact.old_models import ContactVNone, ContactV1
from go.vumitools.tests.helpers import VumiApiHelper


class TestContact(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = self.add_helper(
            PersistenceHelper(use_riak=True))
        riak_manager = self.persistence_helper.get_riak_manager()
        self.add_cleanup(riak_manager.close_manager)
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
            if not isinstance(index, tuple):
                index = (index.get_field(), index.get_value())
            if index[0] == index_name:
                index_values.append(index[1])
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
        self.add_cleanup(riak_manager.close_manager)
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
    def test_contact_for_field_msisdn(self):
        contact = yield self.contact_store.new_contact(
            name=u'name', msisdn=u'+123456')
        found_contact = yield self.contact_store.contact_for_addr_field(
            'msisdn', u'+123456', create=False)
        self.assertEqual(contact.key, found_contact.key)

    @inlineCallbacks
    def test_contact_for_field_not_found(self):
        yield self.contact_store.new_contact(
            name=u'name', msisdn=u'+27831234567')
        self.contact_store.FIND_BY_INDEX_SEARCH_FALLBACK = False
        contact_d = self.contact_store.contact_for_addr_field(
            'msisdn', u'nothing', create=False)
        yield self.assertFailure(contact_d, ContactNotFoundError)

    @inlineCallbacks
    def test_contact_for_addr_gtalk(self):
        contact = yield self.contact_store.new_contact(
            name=u'name', msisdn=u'+27831234567', gtalk_id=u'foo@example.com')
        found_contact = yield self.contact_store.contact_for_addr(
            'gtalk', u'foo@example.com', create=False)
        self.assertEqual(contact.key, found_contact.key)

    @inlineCallbacks
    def test_contact_for_addr_unindexed(self):
        yield self.make_unindexed_contact(name=u'name', msisdn=u'+27831234567')
        contact_d = self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=False)
        yield self.assertFailure(contact_d, ContactNotFoundError)

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
    def test_contact_for_addr_unindexed_fallback_enabled(self):
        contact = yield self.make_unindexed_contact(
            name=u'name', msisdn=u'+27831234567')
        self.contact_store.FIND_BY_INDEX_SEARCH_FALLBACK = True
        found_contact = yield self.contact_store.contact_for_addr(
            'sms', u'+27831234567', create=False)
        self.assertEqual(contact.key, found_contact.key)

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

    @inlineCallbacks
    def test_get_static_contact_keys_for_group(self):
        """
        If we ask for the static keys for a group, we get an IndexPage that we
        can walk until we have all the results.
        """
        store = self.contact_store
        group = yield store.new_group(u'test group')
        contact_keys = set([])
        for i in range(2):
            contact = yield store.new_contact(
                name=u'Contact', surname=u'%d' % i, msisdn=u'12345',
                groups=[group])
            contact_keys.add(contact.key)

        index_page = yield store.get_static_contact_keys_for_group(group)
        self.assertEqual(len(list(index_page)), 2)
        self.assertEqual(index_page.has_next_page(), False)

    @inlineCallbacks
    def test_get_dynamic_contact_keys_for_group(self):
        """
        If we ask for the dynamic keys for a group, we get a PaginatedSearch
        that we can walk until we have all the results.
        """
        store = self.contact_store
        group = yield store.new_smart_group(u'test group', u'surname:"Foo 1"')
        matching_contact = yield store.new_contact(
            name=u'Contact', surname=u'Foo 1', msisdn=u'12345')
        yield store.new_contact(
            name=u'Contact', surname=u'Foo 2', msisdn=u'12345')

        index_page = yield store.get_dynamic_contact_keys_for_group(group)
        self.assertEqual(list(index_page), [matching_contact.key])
        self.assertEqual(index_page.has_next_page(), True)

    @inlineCallbacks
    def test_get_contact_keys_for_group_static(self):
        """
        If we ask for the keys for a static group, we get an IndexPage that we
        can walk until we have all the results.
        """
        store = self.contact_store
        group = yield store.new_group(u'test group')
        contact_keys = set([])
        for i in range(2):
            contact = yield store.new_contact(
                name=u'Contact', surname=u'%d' % i, msisdn=u'12345',
                groups=[group])
            contact_keys.add(contact.key)

        index_page = yield store.get_contact_keys_for_group(group)
        self.assertEqual(len(list(index_page)), 2)
        self.assertEqual(index_page.has_next_page(), False)

    @inlineCallbacks
    def test_get_contact_keys_for_dynamic_group(self):
        """
        If we ask for the keys for a dynamic group, we get a wrapper around a
        PaginatedSearch and an empty IndexPage that we can walk until we have
        all the results.
        """
        store = self.contact_store
        group = yield store.new_smart_group(u'test group', u'surname:"Foo 1"')
        matching_contact = yield store.new_contact(
            name=u'Contact', surname=u'Foo 1', msisdn=u'12345')
        yield store.new_contact(
            name=u'Contact', surname=u'Foo 2', msisdn=u'12345')

        first_page = yield store.get_contact_keys_for_group(group)
        self.assertEqual(list(first_page), [matching_contact.key])
        # This is the empty last page of the search results.
        second_page = yield first_page.next_page()
        self.assertEqual(list(second_page), [])
        # This is the empty only page of the index results.
        third_page = yield second_page.next_page()
        self.assertEqual(list(third_page), [])
        self.assertEqual(third_page.has_next_page(), False)

    @inlineCallbacks
    def test_get_contact_keys_for_mixed_group(self):
        """
        If we ask for the keys for a group that is both static and dynamic, we
        get a wrapper around a PaginatedSearch and an IndexPage that we can
        walk until we have all the results.
        """
        store = self.contact_store
        group = yield store.new_smart_group(u'test group', u'surname:"Foo 1"')
        dynamic_contact = yield store.new_contact(
            name=u'Contact', surname=u'Foo 1', msisdn=u'12345')
        static_contact = yield store.new_contact(
            name=u'Contact', surname=u'Foo 2', msisdn=u'12345', groups=[group])
        yield store.new_contact(
            name=u'Contact', surname=u'Foo 3', msisdn=u'12345')

        first_page = yield store.get_contact_keys_for_group(group)
        self.assertEqual(list(first_page), [dynamic_contact.key])
        # This is the empty last page of the search results.
        second_page = yield first_page.next_page()
        self.assertEqual(list(second_page), [])
        # This is the only page of the index results.
        third_page = yield second_page.next_page()
        self.assertEqual(list(third_page), [static_contact.key])
        self.assertEqual(third_page.has_next_page(), False)


class TestPaginatedSearch(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.get_or_create_user()
        riak_manager = self.vumi_helper.get_riak_manager()
        self.add_cleanup(riak_manager.close_manager)
        self.store = ContactStore(riak_manager, self.user_helper.account_key)

    def add_contact(self, **kw):
        params = dict(name=u'First', surname=u'Last', msisdn=u'12345')
        params.update(kw)
        return self.store.new_contact(**params)

    @inlineCallbacks
    def test_paginated_search_no_results(self):
        """
        If our search yields no results, we get an empty PaginatedSearch object
        with no next page.
        """
        zeroth_page = PaginatedSearch(
            self.store.contacts, 10, u'surname:"Foo"', 0, [])
        first_page = yield zeroth_page.next_page()
        self.assertNotEqual(first_page, None)
        self.assertEqual(list(first_page), [])
        self.assertEqual(first_page.has_next_page(), False)
        second_page = yield first_page.next_page()
        self.assertEqual(second_page, None)

    @inlineCallbacks
    def test_paginated_search_one_page_results(self):
        """
        If our search yields one page of results, we get a PaginatedSearch
        object containing the matching keys with an empty next page.
        """
        matching_contacts = [
            (yield self.add_contact(surname=u'Foo')),
            (yield self.add_contact(surname=u'Foo')),
            (yield self.add_contact(surname=u'Foo')),
        ]
        # A non-matching contact that we expect to not see in the results.
        yield self.add_contact(surname=u'Bar')

        zeroth_page = PaginatedSearch(
            self.store.contacts, 10, u'surname:"Foo"', 0, [])
        first_page = yield zeroth_page.next_page()
        self.assertNotEqual(first_page, None)
        self.assertEqual(
            sorted(first_page), sorted(c.key for c in matching_contacts))
        self.assertEqual(first_page.has_next_page(), True)
        second_page = yield first_page.next_page()
        self.assertEqual(list(second_page), [])
        self.assertEqual(second_page.has_next_page(), False)
        third_page = yield second_page.next_page()
        self.assertEqual(third_page, None)

    @inlineCallbacks
    def test_paginated_search_two_page_results(self):
        """
        If our search yields two pages of results, we get a PaginatedSearch
        object containing the matching keys with an empty last page.
        """
        matching_contacts = [
            (yield self.add_contact(surname=u'Foo')),
            (yield self.add_contact(surname=u'Foo')),
            (yield self.add_contact(surname=u'Foo')),
            (yield self.add_contact(surname=u'Foo')),
        ]
        # A non-matching contact that we expect to not see in the results.
        yield self.add_contact(surname=u'Bar')

        zeroth_page = PaginatedSearch(
            self.store.contacts, 3, u'surname:"Foo"', 0, [])
        first_page = yield zeroth_page.next_page()

        first_keys = list(first_page)
        self.assertEqual(len(first_keys), 3)
        second_page = yield first_page.next_page()
        second_keys = list(second_page)
        self.assertEqual(len(second_keys), 1)
        third_page = yield second_page.next_page()
        self.assertEqual(list(third_page), [])
        self.assertEqual(third_page.has_next_page(), False)
        self.assertEqual(
            sorted(first_keys + second_keys),
            sorted(c.key for c in matching_contacts))


class FakeIndexPage(object):
    """
    Fake IndexPage implementation for testing ChainedIndexPages
    """
    def __init__(self, name, *pages):
        self.name = name
        self._pages = pages

    def __iter__(self):
        return iter(self._pages[0])

    def has_next_page(self):
        return len(self._pages) > 1

    def next_page(self):
        pages = self._pages[1:]
        if pages:
            return succeed(type(self)(self.name, *pages))
        else:
            return succeed(None)


class FakeManager(object):
    """
    A fake manager so @Manager.calls_manager works.
    """
    call_decorator = staticmethod(inlineCallbacks)


class TestChainedIndexPages(VumiTestCase):

    @inlineCallbacks
    def test_one_empty_page(self):
        """
        If given a single empty page, ChainedIndexPage merely proxies it.
        """
        first_page = ChainedIndexPages(
            FakeManager, FakeIndexPage("empty", []))
        self.assertEqual(list(first_page), [])
        self.assertEqual(first_page.has_next_page(), False)
        second_page = yield first_page.next_page()
        self.assertEqual(second_page, None)

    @inlineCallbacks
    def test_one_full_page(self):
        """
        If given a single full page, ChainedIndexPage merely proxies it.
        """
        first_page = ChainedIndexPages(
            FakeManager, FakeIndexPage("single", ["foo"]))
        self.assertEqual(list(first_page), ["foo"])
        self.assertEqual(first_page.has_next_page(), False)
        second_page = yield first_page.next_page()
        self.assertEqual(second_page, None)

    @inlineCallbacks
    def test_one_multiple_page(self):
        """
        If given a single page that has next pages, ChainedIndexPage merely
        proxies it.
        """
        first_page = ChainedIndexPages(
            FakeManager, FakeIndexPage("multi", ["foo"], ["bar"]))
        self.assertEqual(list(first_page), ["foo"])
        self.assertEqual(first_page.has_next_page(), True)
        second_page = yield first_page.next_page()
        self.assertEqual(list(second_page), ["bar"])
        self.assertEqual(second_page.has_next_page(), False)
        third_page = yield second_page.next_page()
        self.assertEqual(third_page, None)

    @inlineCallbacks
    def test_two_empty_pages(self):
        """
        If given a two empty pages, ChainedIndexPage proxies the first and then
        the second.
        """
        first_page = ChainedIndexPages(
            FakeManager, FakeIndexPage("empty1", []),
            FakeIndexPage("empty2", []))
        self.assertEqual(list(first_page), [])
        self.assertEqual(first_page.has_next_page(), True)
        self.assertEqual(first_page._current_page.name, "empty1")

        second_page = yield first_page.next_page()
        self.assertEqual(list(second_page), [])
        self.assertEqual(second_page.has_next_page(), False)
        self.assertEqual(second_page._current_page.name, "empty2")

        third_page = yield second_page.next_page()
        self.assertEqual(third_page, None)

    @inlineCallbacks
    def test_two_full_pages(self):
        """
        If given two full pages, ChainedIndexPage proxies the first and then
        the second.
        """
        first_page = ChainedIndexPages(
            FakeManager, FakeIndexPage("full1", ["foo"]),
            FakeIndexPage("full2", ["bar"]))
        self.assertEqual(list(first_page), ["foo"])
        self.assertEqual(first_page.has_next_page(), True)
        self.assertEqual(first_page._current_page.name, "full1")

        second_page = yield first_page.next_page()
        self.assertEqual(list(second_page), ["bar"])
        self.assertEqual(second_page.has_next_page(), False)
        self.assertEqual(second_page._current_page.name, "full2")

        third_page = yield second_page.next_page()
        self.assertEqual(third_page, None)

    @inlineCallbacks
    def test_two_multiple_pages(self):
        """
        If given two pages that each have next pages, ChainedIndexPage proxies
        the first and then the second.
        """
        first_page = ChainedIndexPages(
            FakeManager, FakeIndexPage("multi1", ["foo"], ["bar"]),
            FakeIndexPage("multi2", ["baz"], ["quux"]))
        self.assertEqual(list(first_page), ["foo"])
        self.assertEqual(first_page.has_next_page(), True)
        self.assertEqual(first_page._current_page.name, "multi1")
        second_page = yield first_page.next_page()
        self.assertEqual(list(second_page), ["bar"])
        self.assertEqual(second_page.has_next_page(), True)
        self.assertEqual(second_page._current_page.name, "multi1")

        third_page = yield second_page.next_page()
        self.assertEqual(list(third_page), ["baz"])
        self.assertEqual(third_page.has_next_page(), True)
        self.assertEqual(third_page._current_page.name, "multi2")
        fourth_page = yield third_page.next_page()
        self.assertEqual(list(fourth_page), ["quux"])
        self.assertEqual(fourth_page.has_next_page(), False)
        self.assertEqual(fourth_page._current_page.name, "multi2")

        fifth_page = yield fourth_page.next_page()
        self.assertEqual(fifth_page, None)

    @inlineCallbacks
    def test_page_mix(self):
        """
        If given an assortment of pages, ChainedIndexPage proxies each in turn.
        """
        first_page = ChainedIndexPages(
            FakeManager, FakeIndexPage("multi", ["foo"], ["bar"]),
            FakeIndexPage("empty", []), FakeIndexPage("full", ["baz"]))
        self.assertEqual(list(first_page), ["foo"])
        self.assertEqual(first_page.has_next_page(), True)
        self.assertEqual(first_page._current_page.name, "multi")
        second_page = yield first_page.next_page()
        self.assertEqual(list(second_page), ["bar"])
        self.assertEqual(second_page.has_next_page(), True)
        self.assertEqual(second_page._current_page.name, "multi")

        third_page = yield second_page.next_page()
        self.assertEqual(list(third_page), [])
        self.assertEqual(third_page.has_next_page(), True)
        self.assertEqual(third_page._current_page.name, "empty")

        fourth_page = yield third_page.next_page()
        self.assertEqual(list(fourth_page), ["baz"])
        self.assertEqual(fourth_page.has_next_page(), False)
        self.assertEqual(fourth_page._current_page.name, "full")

        fifth_page = yield fourth_page.next_page()
        self.assertEqual(fifth_page, None)
