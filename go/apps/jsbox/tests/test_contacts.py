# -*- coding: utf-8 -*-

from mock import Mock
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.contacts import ContactsResource
from go.vumitools.tests.utils import GoPersistenceMixin
from go.vumitools.account import AccountStore
from go.vumitools.contact import ContactStore


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.user_api = Mock()

    def user_api_for_api(self, api):
        return self.user_api


class TestContactsResource(ResourceTestCaseBase, GoPersistenceMixin):
    use_riak = True
    app_worker_cls = StubbedAppWorker
    resource_cls = ContactsResource

    @inlineCallbacks
    def setUp(self):
        super(TestContactsResource, self).setUp()
        yield self._persist_setUp()

        # We pass `self` in as the VumiApi object here, because mk_user() just
        # grabs .account_store off it.
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        self.account = yield self.mk_user(self, u'user')
        self.contact_store = ContactStore.from_user_account(self.account)
        yield self.contact_store.contacts.enable_search()

        self.app_worker.user_api.contact_store = self.contact_store
        yield self.create_resource({'delivery_class': u'sms'})

    def tearDown(self):
        super(TestContactsResource, self).tearDown()
        return self._persist_tearDown()

    def check_reply(self, reply, **kw):
        kw.setdefault('success', True)
        for key, expected_value in kw.iteritems():
            self.assertEqual(reply[key], expected_value)

    def check_contact_reply(self, reply, **expected_fields):
        for field_name, expected_value in expected_fields.iteritems():
            self.assertEqual(reply['contact'][field_name], expected_value)
        self.check_reply(reply)

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
        self.check_contact_reply(
            reply,
            key=contact.key,
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

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
        self.check_contact_reply(
            reply,
            key=contact.key,
            name=u'Zoë',
            surname=u'Person',
            msisdn=u'+27831234567')

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

        self.check_contact_reply(
            reply,
            key=contact.key,
            name=u'A Random',
            surname=u'Person',
            twitter_handle=u'random',
            msisdn=u'unknown')

    @inlineCallbacks
    def test_handle_get_or_create(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')
        reply = yield self.dispatch_command('get_or_create',
                                            addr=u'+27831234567')

        self.check_reply(reply, created=False)
        self.check_contact_reply(
            reply,
            key=contact.key,
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

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
        self.check_reply(reply, created=False)
        self.check_contact_reply(
            reply,
            key=contact.key,
            name=u'Zoë',
            surname=u'Person',
            msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_or_create_for_nonexistent_contact(self):
        reply = yield self.dispatch_command('get_or_create',
                                            addr=u'+27831234567')

        self.check_reply(reply, created=True)
        self.check_contact_fields(reply['contact']['key'],
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

        self.check_reply(reply, created=False)
        self.check_contact_reply(
            reply,
            key=contact.key,
            name=u'A Random',
            surname=u'Person',
            twitter_handle=u'random',
            msisdn=u'unknown')

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
        self.check_reply(reply)

        self.check_contact_fields(
            contact.key,
            name=u'A Random',
            surname=u'Jackal',
            msisdn=u'+27831234567',
            groups=[u'group-a', u'group-b', u'group-c'])

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
            'update', key=contact.key, fields={'surname': u'Robot'})
        self.check_reply(reply)

        self.check_contact_fields(
            contact.key,
            name=u'A Random',
            surname=u'Robot',
            msisdn=u'+27831234567')

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
        self.check_reply(reply)

        self.check_contact_fields(contact.key, **{
            'msisdn': u'+27831234567',
            'extras-a': u'one',
            'extras-b': u'2',
            'extras-c': u'three',
            'extras-d': u'four',
        })

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
        self.check_reply(reply)

        self.check_contact_fields(contact.key, **{
            'msisdn': u'+27831234567',
            'extras-foo': u'☃',
            'extras-lorem': u'ipsum',
        })

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
        self.check_reply(reply)

        self.check_contact_fields(contact.key, **{
            'msisdn': u'+27831234567',
            'subscription-a': u'one',
            'subscription-b': u'2',
            'subscription-c': u'three',
            'subscription-d': u'four',
        })

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
            'update_subscriptions',
            key=contact.key,
            fields={'location': None})

    @inlineCallbacks
    def test_handle_update_subscriptions_for_unicode_chars(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            subscription={u'foo': u'bar', u'lorem': u'ipsum'})

        reply = yield self.dispatch_command(
            'update_subscriptions',
            key=contact.key,
            fields={'foo': u'☃'})
        self.check_reply(reply)

        self.check_contact_fields(contact.key, **{
            'msisdn': u'+27831234567',
            'subscription-foo': u'☃',
            'subscription-lorem': u'ipsum',
        })

    def test_handle_update_subscriptions_for_nonexistent_contacts(self):
        return self.assert_bad_command(
            'update_subscriptions',
            key='213123',
            fields={'foo': u'bar'})

    @inlineCallbacks
    def test_handle_new(self):
        reply = yield self.dispatch_command('new', contact={
            'name': u'A Random',
            'surname': u'Jackal',
            'msisdn': u'+27831234567',
        })

        self.check_contact_reply(reply)

    @inlineCallbacks
    def test_handle_new_parsing(self):
        yield self.assert_bad_command('new')
        yield self.assert_bad_command('new', contact=2)
        yield self.assert_bad_command('new', contact=None)

    @inlineCallbacks
    def test_handle_new_for_unicode_chars(self):
        reply = yield self.dispatch_command('new', contact={
            'name': u'A Random',
            'surname': u'Robot',
            'msisdn': u'+27831234567',
        })

        self.check_contact_reply(reply)

    @inlineCallbacks
    def test_handle_save(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Jackal',
            msisdn=u'+27831234567',
            extra={u'foo': u'bar', u'lorem': u'ipsum'})

        reply = yield self.dispatch_command('save', contact={
            'key': contact.key,
            'surname': u'Robot',
            'msisdn': u'unknown',
            'extra': {u'baz': u'qux'}
        })

        self.check_contact_reply(reply)
        self.check_contact_fields(contact.key, **{
            'name': None,
            'surname': u'Robot',
            'msisdn': u'unknown',
            'extras-baz': u'qux',
        })

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

        reply = yield self.dispatch_command('save', contact={
            'key': contact.key,
            'surname': u'☃',
            'msisdn': u'+27831234567',
            'groups': [u'group-a', u'group-c'],
        })

        self.check_contact_reply(reply)
        self.check_contact_fields(
            contact.key,
            surname=u'☃',
            msisdn=u'+27831234567',
            groups=[u'group-a', u'group-c'])

    def test_handle_save_for_nonexistent_contacts(self):
        return self.assert_bad_command('save', contact={'key': u'213123'})
