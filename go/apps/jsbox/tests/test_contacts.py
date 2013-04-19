# -*- coding: utf-8 -*-

from mock import Mock
from twisted.internet.defer import inlineCallbacks

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
        yield self.create_resource({'delivery_class': 'sms'})

    def tearDown(self):
        super(TestContactsResource, self).tearDown()
        return self._persist_tearDown()

    def check_reply(self, reply, **kw):
        kw.setdefault('success', True)
        for key, expected_value in kw.iteritems():
            self.assertEqual(reply[key], expected_value)

    def check_contact_reply(self, reply, **fields):
        for field_name, expected_value in fields.iteritems():
            self.assertEqual(reply['contact'][field_name], expected_value)
        self.check_reply(reply)

    def new_contact(self, **fields):
        return self.contact_store.new_contact(**fields)

    @inlineCallbacks
    def test_handle_get(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')
        reply = yield self.dispatch_command('get', addr=u'+27831234567')
        self.check_contact_reply(reply,
            key=contact.key,
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_for_unicode_chars(self):
        contact = yield self.new_contact(
            name=u'Zoë',
            surname=u'Person',
            msisdn=u'+27831234567')
        reply = yield self.dispatch_command('get', addr=u'+27831234567')
        self.check_contact_reply(reply,
            key=contact.key,
            name=u'Zoë',
            surname=u'Person',
            msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_for_nonexistent_contact(self):
        reply = yield self.dispatch_command('get', addr=u'+27831234567')
        self.check_reply(reply, success=False)

    @inlineCallbacks
    def test_handle_get_for_overriden_delivery_class(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            twitter_handle=u'random',
            msisdn=u'unknown')

        reply = yield self.dispatch_command('get',
            addr=u'random',
            delivery_class=u'twitter')

        self.check_contact_reply(reply,
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
        self.check_contact_reply(reply,
            key=contact.key,
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_or_create_for_unicode_chars(self):
        contact = yield self.new_contact(
            name=u'Zoë',
            surname=u'Person',
            msisdn=u'+27831234567')
        reply = yield self.dispatch_command('get_or_create',
                                            addr=u'+27831234567')
        self.check_contact_reply(reply,
            key=contact.key,
            name=u'Zoë',
            surname=u'Person',
            msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_or_create_for_nonexistent_contact(self):
        reply = yield self.dispatch_command('get_or_create',
                                            addr=u'+27831234567')
        self.check_contact_reply(reply, msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_get_or_create_for_overriden_delivery_class(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            twitter_handle=u'random',
            msisdn=u'unknown')

        reply = yield self.dispatch_command('get_or_create',
            addr=u'random',
            delivery_class=u'twitter')

        self.check_contact_reply(reply,
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
            msisdn=u'+27831234567')

        reply = yield self.dispatch_command('update',
            key=contact.key,
            surname=u'Jackal')

        self.check_contact_reply(reply,
            key=contact.key,
            name=u'A Random',
            surname=u'Jackal',
            msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_update_for_unicode_chars(self):
        contact = yield self.new_contact(
            name=u'A Random',
            surname=u'Person',
            msisdn=u'+27831234567')

        reply = yield self.dispatch_command('update',
            key=contact.key,
            surname=u'☃')

        self.check_contact_reply(reply,
            key=contact.key,
            name=u'A Random',
            surname=u'☃',
            msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_update_for_nonexistent_contacts(self):
        reply = yield self.dispatch_command('update', key='213123')
        self.check_reply(reply, success=False)

    @inlineCallbacks
    def test_handle_update_extra(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            extra={'foo': u'bar', 'lorem': u'ipsum'})

        reply = yield self.dispatch_command('update_extra',
            key=contact.key,
            field='foo',
            value=u'larp')

        self.check_contact_reply(reply, **{
            'key': contact.key,
            'msisdn': u'+27831234567',
            'extras-foo': u'larp',
            'extras-lorem': u'ipsum',
        })

    @inlineCallbacks
    def test_handle_update_extra_for_unicode_chars(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            extra={'foo': u'bar', 'lorem': u'ipsum'})

        reply = yield self.dispatch_command('update_extra',
            key=contact.key,
            field='foo',
            value=u'☃')

        self.check_contact_reply(reply, **{
            'key': contact.key,
            'msisdn': u'+27831234567',
            'extras-foo': u'☃',
            'extras-lorem': u'ipsum',
        })

    @inlineCallbacks
    def test_handle_update_extra_for_nonexistent_contacts(self):
        reply = yield self.dispatch_command('update_extra',
            key='213123',
            field='foo',
            value=u'bar')
        self.check_reply(reply, success=False)

    @inlineCallbacks
    def test_handle_update_subscription(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            subscription={'foo': u'bar', 'lorem': u'ipsum'})

        reply = yield self.dispatch_command('update_subscription',
            key=contact.key,
            field='foo',
            value=u'larp')

        self.check_contact_reply(reply, **{
            'key': contact.key,
            'msisdn': u'+27831234567',
            'subscription-foo': u'larp',
            'subscription-lorem': u'ipsum',
        })

    @inlineCallbacks
    def test_handle_update_subscription_for_unicode_chars(self):
        contact = yield self.new_contact(
            msisdn=u'+27831234567',
            subscription={'foo': u'bar', 'lorem': u'ipsum'})

        reply = yield self.dispatch_command('update_subscription',
            key=contact.key,
            field='foo',
            value=u'☃')

        self.check_contact_reply(reply, **{
            'key': contact.key,
            'msisdn': u'+27831234567',
            'subscription-foo': u'☃',
            'subscription-lorem': u'ipsum',
        })

    @inlineCallbacks
    def test_handle_update_subscription_for_nonexistent_contacts(self):
        reply = yield self.dispatch_command('update_subscription',
            key='21312',
            field='foo',
            value=u'bar')
        self.check_reply(reply, success=False)

    @inlineCallbacks
    def test_handle_new(self):
        reply = yield self.dispatch_command('new',
            name=u'A Random',
            surname=u'Jackal',
            msisdn=u'+27831234567')

        self.check_contact_reply(reply,
            name=u'A Random',
            surname=u'Jackal',
            msisdn=u'+27831234567')

    @inlineCallbacks
    def test_handle_new_for_unicode_chars(self):
        reply = yield self.dispatch_command('new',
            name=u'A Random',
            surname=u'☃',
            msisdn=u'+27831234567')

        self.check_contact_reply(reply,
            name=u'A Random',
            surname=u'☃',
            msisdn=u'+27831234567')
