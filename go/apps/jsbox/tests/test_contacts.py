# -*- coding: utf-8 -*-

import json

from twisted.internet.defer import inlineCallbacks, returnValue

from vxsandbox.tests.utils import DummyAppWorker
from vxsandbox.resources.tests.utils import ResourceTestCaseBase

from go.apps.jsbox.contacts import ContactsResource, GroupsResource
from go.vumitools.tests.helpers import VumiApiHelper


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.user_api = None

    def user_api_for_api(self, api):
        return self.user_api


class TestContactsResource(ResourceTestCaseBase):
    # TODO: Make this resource stuff into a helper in vumi.
    app_worker_cls = StubbedAppWorker
    resource_cls = ContactsResource

    @inlineCallbacks
    def setUp(self):
        super(TestContactsResource, self).setUp()

        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u"user")
        self.app_worker.user_api = self.user_helper.user_api
        self.contact_store = self.user_helper.user_api.contact_store

        yield self.create_resource({'delivery_class': u'sms'})

    def check_reply(self, reply, **kw):
        kw.setdefault('success', True)

        # get a dict of the reply fields that we can pop items off without
        # worrying about modifying the actual reply
        reply = json.loads(reply.to_json())

        contact_fields = reply.pop('contact', {})
        expected_contact_fields = kw.pop('contact', {})
        for field_name, expected_value in expected_contact_fields.iteritems():
            self.assertEqual(contact_fields[field_name], expected_value)

        for field_name, expected_value in kw.iteritems():
            self.assertEqual(reply[field_name], expected_value)

    @inlineCallbacks
    def assert_bad_command(self, cmd, **kw):
        reply = yield self.dispatch_command(cmd, **kw)
        self.check_reply(reply, success=False)

    @inlineCallbacks
    def check_contact_fields(self, key, **expected_fields):
        contact = yield self.contact_store.get_contact_by_key(key)
        fields = yield contact.get_data()
        for field_name, expected_value in expected_fields.iteritems():
            self.assertEqual(fields[field_name], expected_value)

    @inlineCallbacks
    def new_contact(self, **fields):
        groups = fields.pop('groups', [])
        contact = yield self.contact_store.new_contact(**fields)
        for group in groups:
            contact.add_to_group(group)
        yield contact.save()
        returnValue(contact)

    @inlineCallbacks
    def test_handle_get(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')
        reply = yield self.dispatch_command('get', addr=u'+27831234567')
        self.check_reply(reply, contact={
            'key': contact.key,
            'name': u'A Random',
            'surname': u'Person',
            'msisdn': u'+27831234567',
        })

    @inlineCallbacks
    def test_handle_get_parsing(self):
        yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

        yield self.assert_bad_command('get')
        yield self.assert_bad_command('get', delivery_class=u'sms', addr=2)
        yield self.assert_bad_command(
            'get', delivery_class=None, msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_for_unicode_chars(self):
        contact = yield self.new_contact(
            name=u'Zoë',
            surname=u'Person',
            msisdn=u'+27831234567')
        reply = yield self.dispatch_command('get', addr=u'+27831234567')
        self.check_reply(reply, contact={
            'key': contact.key,
            'name': u'Zoë',
            'surname': u'Person',
            'msisdn': u'+27831234567',
        })

    def test_handle_get_for_nonexistent_contact(self):
        return self.assert_bad_command('get', addr=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_for_overriden_delivery_class(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            twitter_handle=u'random',
            msisdn=u'unknown')

        reply = yield self.dispatch_command(
            'get',
            addr=u'random',
            delivery_class=u'twitter')

        self.check_reply(reply, contact={
            'key': contact.key,
            'name': u'A Random',
            'surname': u'Person',
            'twitter_handle': u'random',
            'msisdn': u'unknown',
        })

    @inlineCallbacks
    def test_handle_get_or_create(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')
        reply = yield self.dispatch_command('get_or_create',
                                            addr=u'+27831234567')

        self.check_reply(reply, created=False, contact={
            'key': contact.key,
            'name': u'A Random',
            'surname': u'Person',
            'msisdn': u'+27831234567',
        })

    @inlineCallbacks
    def test_handle_get_or_create_parsing(self):
        yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

        yield self.assert_bad_command('get_or_create')
        yield self.assert_bad_command(
            'get_or_create', delivery_class=u'sms', addr=2)
        yield self.assert_bad_command(
            'get_or_create', delivery_class=None, msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_or_create_for_unicode_chars(self):
        contact = yield self.new_contact(
            name=u'Zoë',
            surname=u'Person',
            msisdn=u'+27831234567')
        reply = yield self.dispatch_command('get_or_create',
                                            addr=u'+27831234567')
        self.check_reply(reply, created=False, contact={
            'key': contact.key,
            'name': u'Zoë',
            'surname': u'Person',
            'msisdn': u'+27831234567',
        })

    @inlineCallbacks
    def test_handle_get_or_create_for_nonexistent_contact(self):
        reply = yield self.dispatch_command('get_or_create',
                                            addr=u'+27831234567')

        self.check_reply(
            reply,
            created=True,
            contact={'msisdn': u'+27831234567'})
        yield self.check_contact_fields(reply['contact']['key'],
                                        msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_or_create_for_overriden_delivery_class(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            twitter_handle=u'random',
            msisdn=u'unknown')

        reply = yield self.dispatch_command(
            'get_or_create',
            addr=u'random',
            delivery_class=u'twitter')

        self.check_reply(reply, contact={
            'key': contact.key,
            'name': u'A Random',
            'surname': u'Person',
            'twitter_handle': u'random',
            'msisdn': u'unknown',
        })

    @inlineCallbacks
    def test_handle_update(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567',
            groups=[u'group-a', u'group-b'])

        reply = yield self.dispatch_command('update', key=contact.key, fields={
            'surname': u'Jackal',
            'groups': [u'group-a', u'group-c'],
        })

        expected_contact_fields = {
            'key': contact.key,
            'name': u'A Random',
            'surname': u'Jackal',
            'msisdn': u'+27831234567',
            'groups': [u'group-a', u'group-b', u'group-c'],
        }
        self.check_reply(reply, contact=expected_contact_fields)
        yield self.check_contact_fields(**expected_contact_fields)

    @inlineCallbacks
    def test_handle_update_parsing(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

        yield self.assert_bad_command('update')
        yield self.assert_bad_command('update', key=None, fields={})
        yield self.assert_bad_command('update', key=contact.key, fields=2)

    @inlineCallbacks
    def test_handle_update_for_unicode_chars(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

        reply = yield self.dispatch_command(
            'update', key=contact.key, fields={'surname': u'☃'})

        expected_contact_fields = {
            'key': contact.key,
            'name': u'A Random',
            'surname': u'☃',
            'msisdn': u'+27831234567',
        }
        self.check_reply(reply, contact=expected_contact_fields)
        yield self.check_contact_fields(**expected_contact_fields)

    def test_handle_update_for_nonexistent_contacts(self):
        return self.assert_bad_command('update', key='213123', fields={})

    @inlineCallbacks
    def test_handle_update_extras(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            extra={'a': u'1', 'b': u'2', 'c': u'3'})

        reply = yield self.dispatch_command(
            'update_extras',
            key=contact.key,
            fields={'a': u'one', 'c': u'three', 'd': u'four'})

        expected_contact_fields = {
            'key': contact.key,
            'msisdn': u'+27831234567',
            'extras-a': u'one',
            'extras-b': u'2',
            'extras-c': u'three',
            'extras-d': u'four',
        }
        self.check_reply(reply, contact=expected_contact_fields)
        yield self.check_contact_fields(**expected_contact_fields)

    @inlineCallbacks
    def test_handle_update_extras_parsing(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

        yield self.assert_bad_command('update_extras')
        yield self.assert_bad_command(
            'update_extras', key=None, fields={'location': u'CPT'})
        yield self.assert_bad_command(
            'update_extras', key=contact.key, fields={'location': None})

    @inlineCallbacks
    def test_handle_update_extras_for_unicode_chars(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            extra={u'foo': u'bar', u'lorem': u'ipsum'})

        reply = yield self.dispatch_command(
            'update_extras',
            key=contact.key,
            fields={'foo': u'☃'})

        expected_contact_fields = {
            'key': contact.key,
            'msisdn': u'+27831234567',
            'extras-foo': u'☃',
            'extras-lorem': u'ipsum',
        }
        self.check_reply(reply, contact=expected_contact_fields)
        yield self.check_contact_fields(**expected_contact_fields)

    def test_handle_update_extras_for_nonexistent_contacts(self):
        return self.assert_bad_command(
            'update_extras',
            key='213123',
            fields={'foo': u'bar'})

    @inlineCallbacks
    def test_handle_update_subscriptions(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            subscription={'a': u'1', 'b': u'2', 'c': u'3'})

        reply = yield self.dispatch_command(
            'update_subscriptions',
            key=contact.key,
            fields={'a': u'one', 'c': u'three', 'd': u'four'})

        expected_contact_fields = {
            'key': contact.key,
            'msisdn': u'+27831234567',
            'subscription-a': u'one',
            'subscription-b': u'2',
            'subscription-c': u'three',
            'subscription-d': u'four',
        }
        self.check_reply(reply, contact=expected_contact_fields)
        yield self.check_contact_fields(**expected_contact_fields)

    @inlineCallbacks
    def test_handle_update_subscriptions_parsing(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

        yield self.assert_bad_command('update_subscriptions')
        yield self.assert_bad_command(
            'update_subscriptions', key=None, fields={'location': u'CPT'})
        yield self.assert_bad_command(
            'update_subscriptions', key=contact.key, fields={'location': None})

    @inlineCallbacks
    def test_handle_update_subscriptions_for_unicode_chars(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            subscription={u'foo': u'bar', u'lorem': u'ipsum'})

        reply = yield self.dispatch_command(
            'update_subscriptions',
            key=contact.key,
            fields={'foo': u'☃'})

        expected_contact_fields = {
            'key': contact.key,
            'msisdn': u'+27831234567',
            'subscription-foo': u'☃',
            'subscription-lorem': u'ipsum',
        }
        self.check_reply(reply, contact=expected_contact_fields)
        yield self.check_contact_fields(**expected_contact_fields)

    def test_handle_update_subscriptions_for_nonexistent_contacts(self):
        return self.assert_bad_command(
            'update_subscriptions',
            key='213123',
            fields={'foo': u'bar'})

    @inlineCallbacks
    def test_handle_new(self):
        contact_fields = {
            'name': u'A Random',
            'surname': u'Jackal',
            'msisdn': u'+27831234567',
        }
        reply = yield self.dispatch_command('new', contact=contact_fields)
        self.check_reply(reply, contact=contact_fields)

    @inlineCallbacks
    def test_handle_new_parsing(self):
        yield self.assert_bad_command('new')
        yield self.assert_bad_command('new', contact=2)
        yield self.assert_bad_command('new', contact=None)

    @inlineCallbacks
    def test_handle_new_for_unicode_chars(self):
        contact_fields = {
            'name': u'A Random',
            'surname': u'☃',
            'msisdn': u'+27831234567',
        }
        reply = yield self.dispatch_command('new', contact=contact_fields)
        self.check_reply(reply, contact=contact_fields)

    @inlineCallbacks
    def test_handle_save(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Jackal',
            msisdn=u'+27831234567',
            groups=['a', 'b', 'c'],
            extra={u'foo': u'bar', u'lorem': u'ipsum'})

        reply = yield self.dispatch_command('save', contact={
            'key': contact.key,
            'surname': u'Robot',
            'msisdn': u'unknown',
            'groups': ['a', 'd', 'f'],
            'extra': {u'baz': u'qux'},
        })

        expected_contact_fields = {
            'key': contact.key,
            'surname': u'Robot',
            'msisdn': u'unknown',
            'groups': ['a', 'd', 'f'],
            'extras-baz': u'qux',
        }
        self.check_reply(reply, contact=expected_contact_fields)
        yield self.check_contact_fields(**expected_contact_fields)

    @inlineCallbacks
    def test_handle_save_parsing(self):
        yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

        yield self.assert_bad_command('update')
        yield self.assert_bad_command('update', contact=None)
        yield self.assert_bad_command('update', contact={})
        yield self.assert_bad_command('update', contact={'key': None})

    @inlineCallbacks
    def test_handle_save_for_unicode_chars(self):
        contact = yield self.new_contact(
            surname=u'Jackal',
            msisdn=u'+27831234567',
            groups=[u'group-a', u'group-b'])

        new_contact_fields = {
            'key': contact.key,
            'surname': u'☃',
            'msisdn': u'+27831234567',
            'groups': [u'group-a', u'group-c'],
        }
        reply = yield self.dispatch_command('save', contact=new_contact_fields)

        self.check_reply(reply, contact=new_contact_fields)
        yield self.check_contact_fields(**new_contact_fields)

    def test_handle_save_for_nonexistent_contacts(self):
        return self.assert_bad_command('save', contact={'key': u'213123'})

    @inlineCallbacks
    def test_handle_search(self):
        contact = yield self.new_contact(
            surname=u'Jackal',
            msisdn=u'+27831234567',
            groups=[u'group-a', u'group-b'])
        reply = yield self.dispatch_command('search', query=u'surname:Jack*')
        self.assertTrue(reply['success'])
        self.assertFalse('reason' in reply)

        self.assertTrue('keys' in reply)
        self.assertEqual(reply['keys'][0], contact.key)

    @inlineCallbacks
    def test_handle_search_bad_query(self):
        reply = yield self.dispatch_command(
            'search', query=u'name:[BAD_QUERY!]')
        self.assertFalse(reply['success'])
        self.assertFalse('keys' in reply)
        self.assertTrue('reason' in reply)

        self.assertTrue('Error running MapReduce' in reply['reason'])

    @inlineCallbacks
    def test_handle_search_results(self):
        reply = yield self.dispatch_command('search', query=u'name:foo*')
        self.assertTrue(reply['success'])
        self.assertFalse('reason' in reply)
        self.assertEqual(reply['keys'], [])

    @inlineCallbacks
    def test_handle_search_missing_param(self):
        reply = yield self.dispatch_command('search')
        self.assertFalse(reply['success'])
        self.assertTrue('reason' in reply)
        self.assertFalse('keys' in reply)
        self.assertTrue("Expected 'query' field in request" in reply['reason'])

    @inlineCallbacks
    def test_handle_search_max_keys(self):
        keys = set()
        for i in range(0, 6):
            contact = yield self.new_contact(
                surname=unicode('Jackal%s' % i),
                msisdn=u'+27831234567',
                groups=[u'group-a', u'group-b'])
            keys.add(contact.key)

        # subset
        reply = yield self.dispatch_command('search',
                                            query=u'surname:Jack*',
                                            max_keys=3)
        self.assertTrue(reply['success'])
        self.assertEqual(len(reply['keys']), 3)
        self.assertTrue(set(reply['keys']).issubset(keys))

        # no limit
        reply = yield self.dispatch_command('search',
                                            query=u'surname:Jack*')
        self.assertTrue(reply['success'])
        self.assertEqual(set(reply['keys']), keys)

        # bad value for max_keys
        reply = yield self.dispatch_command('search',
                                            query=u'surname:Jack*',
                                            max_keys="Haha!")
        self.assertFalse(reply['success'])
        self.assertTrue(
            "Value for parameter 'max_keys' is invalid" in reply['reason']
        )

    @inlineCallbacks
    def test_handle_get_by_key(self):
        contact = yield self.new_contact(
            surname=u'Jackal',
            msisdn=u'+27831234567',
            groups=[u'group-a', u'group-b'])

        reply = yield self.dispatch_command('get_by_key', key=contact.key)

        self.assertTrue(reply['success'])
        self.assertFalse('reason' in reply)
        self.assertTrue('contact' in reply)

        self.assertEqual(reply['contact']['key'], contact.key)

    @inlineCallbacks
    def test_handle_get_by_key_missing_param(self):
        reply = yield self.dispatch_command('get_by_key')
        self.assertFalse(reply['success'])
        self.assertTrue('reason' in reply)
        self.assertFalse('contact' in reply)
        self.assertTrue("Expected 'key' field in request" in reply['reason'])

    @inlineCallbacks
    def test_handle_get_by_key_no_results(self):
        reply = yield self.dispatch_command('get_by_key', key="Haha!")
        self.assertFalse(reply['success'])
        self.assertTrue('reason' in reply)
        self.assertFalse('contact' in reply)

        self.assertTrue(
            "Contact with key 'Haha!' not found." in reply['reason']
        )


class TestGroupsResource(ResourceTestCaseBase):
    app_worker_cls = StubbedAppWorker
    resource_cls = GroupsResource

    @inlineCallbacks
    def setUp(self):
        super(TestGroupsResource, self).setUp()

        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u"user")
        self.app_worker.user_api = self.user_helper.user_api
        self.contact_store = self.user_helper.user_api.contact_store

        yield self.create_resource({})

    def check_reply(self, reply, **kw):
        kw.setdefault('success', True)

        # get a dict of the reply fields that we can pop items off without
        # worrying about modifying the actual reply
        reply = json.loads(reply.to_json())

        group_fields = reply.pop('group', {})
        expected_group_fields = kw.pop('group', {})
        for field_name, expected_value in expected_group_fields.iteritems():
            self.assertEqual(group_fields[field_name], expected_value)

        for field_name, expected_value in kw.iteritems():
            self.assertEqual(reply[field_name], expected_value)

    @inlineCallbacks
    def new_contact(self, **fields):
        groups = fields.pop('groups', [])
        contact = yield self.contact_store.new_contact(**fields)
        for group in groups:
            contact.add_to_group(group)
        yield contact.save()
        returnValue(contact)

    @inlineCallbacks
    def new_group(self, name, query=None):
        group = yield self.contact_store.new_group(name)
        group.query = query
        yield group.save()
        returnValue(group)

    @inlineCallbacks
    def test_static_handle_search(self):
        group = yield self.new_group(u'foo group')
        reply = yield self.dispatch_command('search', query=u'name:foo*')
        self.assertTrue(reply['success'])
        [gr_data] = reply['groups']
        self.assertEqual(gr_data['key'], group.key)

    @inlineCallbacks
    def test_smart_handle_search(self):
        group = yield self.new_group(u'foo group', query=u'query')
        reply = yield self.dispatch_command('search', query=u'name:foo*')
        self.assertTrue(reply['success'])
        [gr_data] = reply['groups']
        self.assertEqual(gr_data['key'], group.key)
        self.assertEqual(gr_data['query'], group.query)

    @inlineCallbacks
    def test_bad_query_handle_search(self):
        reply = yield self.dispatch_command(
            'search', query=u'name:[BAD_QUERY!]')
        self.assertFalse(reply['success'])
        self.assertTrue('Error running MapReduce' in reply['reason'])

    @inlineCallbacks
    def test_no_results_handle_search(self):
        reply = yield self.dispatch_command('search', query=u'name:foo*')
        self.assertTrue(reply['success'])
        self.assertEqual(reply['groups'], [])

    @inlineCallbacks
    def test_handle_get(self):
        group = yield self.new_group(u'foo group')
        reply = yield self.dispatch_command('get', key=group.key)
        self.assertTrue(reply['success'])
        gr_data = reply['group']
        self.assertEqual(gr_data['key'], group.key)

    @inlineCallbacks
    def test_handle_get_by_name(self):
        group = yield self.new_group(u'foo group')
        reply = yield self.dispatch_command('get_by_name', name=group.name)
        self.assertTrue(reply['success'])
        gr_data = reply['group']
        self.assertEqual(gr_data['key'], group.key)
        self.assertEqual(gr_data['name'], group.name)

    @inlineCallbacks
    def test_multiple_results_handle_get_by_name(self):
        group_name = u'foo group'
        yield self.new_group(group_name)
        yield self.new_group(group_name)
        reply = yield self.dispatch_command('get_by_name', name=group_name)
        self.assertFalse(reply['success'])
        self.assertTrue('Multiple groups found' in reply['reason'])

    @inlineCallbacks
    def test_handle_get_or_create_by_name(self):
        group = yield self.new_group(u'foo group')
        get_reply = yield self.dispatch_command(
            'get_or_create_by_name', name=group.name)
        self.assertTrue(get_reply['success'])
        self.assertFalse(get_reply['created'])

        create_reply = yield self.dispatch_command(
            'get_or_create_by_name', name=u'some other name')
        self.assertTrue(create_reply['success'])
        self.assertTrue(create_reply['created'])

    @inlineCallbacks
    def test_multiple_results_handle_get_or_create(self):
        group_name = u'foo group'
        yield self.new_group(group_name)
        yield self.new_group(group_name)
        reply = yield self.dispatch_command('get_or_create_by_name',
                                            name=group_name)
        self.assertFalse(reply['success'])
        self.assertTrue('Multiple groups found' in reply['reason'])

    @inlineCallbacks
    def test_handle_update(self):
        group = yield self.new_group(u'foo group')
        reply = yield self.dispatch_command(
            'update', key=group.key, name=u'new name', query=u'some query')
        self.assertTrue(reply['success'])
        gr_data = reply['group']
        self.assertEqual(gr_data['name'], 'new name')
        self.assertEqual(gr_data['query'], 'some query')

    @inlineCallbacks
    def test_handle_count_members(self):
        group = yield self.new_group(u'foo group')
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')
        contact.add_to_group(group)
        yield contact.save()
        reply = yield self.dispatch_command(
            'count_members', key=group.key)
        self.assertTrue(reply['success'])
        self.assertEqual(reply['count'], 1)

    @inlineCallbacks
    def test_handle_list(self):
        gr1 = yield self.new_group(u'group 1')
        gr2 = yield self.new_group(u'group 2')
        reply = yield self.dispatch_command('list')
        self.assertTrue(reply['success'])
        self.assertEqual(set(['group 1', 'group 2']),
                         set([gr['name'] for gr in reply['groups']]))
        self.assertEqual(set([gr1.key, gr2.key]),
                         set([gr['key'] for gr in reply['groups']]))
