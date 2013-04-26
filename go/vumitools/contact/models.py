# -*- test-case-name: go.vumitools.tests.test_contact -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import (Unicode, ManyToMany, ForeignKey, Timestamp,
                                    Dynamic)

from go.vumitools.account import UserAccount, PerAccountStore
from go.vumitools.opt_out import OptOutStore


class ContactError(Exception):
    """Raised when an error occurs accessing or manipulating a Contact"""


class ContactNotFoundError(ContactError):
    """Raised when a contact is not found"""


class ContactGroup(Model):
    """A group of contacts"""
    # key is UUID
    name = Unicode()
    query = Unicode(null=True)
    user_account = ForeignKey(UserAccount)
    created_at = Timestamp(default=datetime.utcnow)

    @Manager.calls_manager
    def add_contacts(self, contacts, save=True):
        for contact in contacts:
            contact.groups.add(self)
            yield contact.save()

    def is_smart_group(self):
        return self.query is not None

    def __unicode__(self):
        return self.name


class Contact(Model):
    """A contact"""
    # key is UUID
    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255, null=True)
    surname = Unicode(max_length=255, null=True)
    email_address = Unicode(null=True)  # EmailField?
    msisdn = Unicode(max_length=255)
    dob = Timestamp(null=True)
    twitter_handle = Unicode(max_length=100, null=True)
    facebook_id = Unicode(max_length=100, null=True)
    bbm_pin = Unicode(max_length=100, null=True)
    gtalk_id = Unicode(null=True)
    created_at = Timestamp(default=datetime.utcnow)
    groups = ManyToMany(ContactGroup)
    extra = Dynamic(prefix='extras-')
    subscription = Dynamic(prefix='subscription-')

    def add_to_group(self, group):
        if isinstance(group, ContactGroup):
            self.groups.add(group)
        else:
            self.groups.add_key(group)

    def addr_for(self, delivery_class):
        # TODO: delivery classes need to be defined somewhere
        if delivery_class in ('sms', 'ussd'):
            return self.msisdn
        elif delivery_class == 'gtalk':
            return self.gtalk_id
        elif delivery_class == 'twitter':
            return self.twitter_handle
        else:
            return None

    def __unicode__(self):
        if self.name and self.surname:
            return u' '.join([self.name, self.surname])
        else:
            return (self.surname or self.name or
                self.gtalk_id or self.twitter_handle or self.msisdn
                or 'Unknown User')


class ContactStore(PerAccountStore):
    NONSETTABLE_CONTACT_FIELDS = ['$VERSION', 'user_account']

    def setup_proxies(self):
        self.contacts = self.manager.proxy(Contact)
        self.groups = self.manager.proxy(ContactGroup)

    @classmethod
    def settable_contact_fields(cls, **fields):
        return dict((k, v) for k, v in fields.iteritems()
                    if k not in cls.NONSETTABLE_CONTACT_FIELDS)

    @Manager.calls_manager
    def new_contact(self, **fields):
        contact_id = uuid4().get_hex()

        # These are foreign keys.
        groups = fields.pop('groups', [])

        contact = self.contacts(
            contact_id, user_account=self.user_account_key,
            **self.settable_contact_fields(**fields))

        for group in groups:
            contact.add_to_group(group)

        yield contact.save()
        returnValue(contact)

    @Manager.calls_manager
    def update_contact(self, key, **fields):
        # These are foreign keys.
        groups = fields.pop('groups', [])
        fields = self.settable_contact_fields(**fields)

        contact = yield self.get_contact_by_key(key)
        for field_name, field_value in fields.iteritems():
            if field_name in contact.field_descriptors:
                setattr(contact, field_name, field_value)

        for group in groups:
            contact.add_to_group(group)

        yield contact.save()
        returnValue(contact)

    @Manager.calls_manager
    def new_group(self, name):
        group_id = uuid4().get_hex()

        # TODO: Do we want to check for name uniqueness?

        group = self.groups(
            group_id, name=name, user_account=self.user_account_key)
        yield group.save()
        returnValue(group)

    @Manager.calls_manager
    def new_smart_group(self, name, query):
        group_id = uuid4().get_hex()
        group = self.groups(group_id, name=name,
            user_account=self.user_account_key, query=query)
        yield group.save()
        returnValue(group)

    @Manager.calls_manager
    def get_contact_by_key(self, key):
        contact = yield self.contacts.load(key)
        if contact is None:
            raise ContactNotFoundError(
                "Contact with key '%s' not found." % key)
        returnValue(contact)

    def get_group(self, name):
        return self.groups.load(name)

    @Manager.calls_manager
    def get_contacts_for_group(self, group):
        """Return contact keys for this group."""
        contacts = set([])
        static_contacts = yield self.get_static_contacts_for_group(group)
        contacts.update(static_contacts)
        if group.is_smart_group():
            dynamic_contacts = yield self.get_dynamic_contacts_for_group(group)
            contacts.update(dynamic_contacts)
        returnValue(list(contacts))

    @Manager.calls_manager
    def get_contacts_for_conversation(self, conversation):
        """
        Collect all contacts relating to a conversation from static &
        dynamic groups.
        """
        # Grab all contacts we can find
        contacts = set([])
        for groups in conversation.groups.load_all_bunches():
            for group in (yield groups):
                group_contacts = yield self.get_contacts_for_group(group)
                contacts.update(group_contacts)

        returnValue(list(contacts))

    def get_static_contacts_for_group(self, group):
        """
        Look up contacts through Riak 2i
        """
        return group.backlinks.contacts()

    def get_dynamic_contacts_for_group(self, group):
        """
        Use Riak search to find matching contacts.
        """
        return self.contacts.raw_search(group.query).get_keys()

    def count_contacts_for_group(self, group):
        if group.is_smart_group():
            return self.contacts.raw_search(group.query).get_count()
        else:
            return self.contacts.index_lookup('groups', group.key).get_count()

    @Manager.calls_manager
    def filter_contacts_on_surname(self, letter, group=None):
        # FIXME: This does a mapreduce over a bucket, which means hitting every
        #        key in riak.
        # TODO: vumi.persist needs to have better ways of supporting
        #       generic map reduce functions. There's a bunch of boilerplate
        #       around getting bucket names and indexes that I'm doing
        #       manually that could be automated.
        mr = self.manager.riak_map_reduce()
        bucket = self.manager.bucket_name(Contact)
        mr.add_bucket(bucket)
        if group is not None:
            mr.index(bucket, 'groups_bin', group.key)
        # Deleted values hang around with tombstone markers in Riak for a while
        # before they get removed, and this happens a lot in tests. We need to
        # find the real values amongst the deleted ones here.
        # TODO: Make this a general thing?
        js_function = """function(value, keyData, arg){
            for (i in value.values) {
                var val = value.values[i]
                if (!val.metadata['X-Riak-Deleted']) {
                    var data = JSON.parse(val.data);
                    if (data.surname) {
                        if (data.surname.toLowerCase()[0] === arg) {
                            return [[value.key, val]];
                        }
                    }
                }
            }
            return [];
        }"""
        mr.map(js_function, {'arg': letter.lower()})
        contacts = yield self.manager.run_map_reduce(mr,
            lambda manager, result: Contact.load(
                manager, result[0], result[1]))
        returnValue(contacts)

    @Manager.calls_manager
    def list_contacts(self):
        # Not stale, because we're using backlinks.
        user_account = yield self.get_user_account()
        returnValue(user_account.backlinks.contacts(self.manager))

    @Manager.calls_manager
    def list_groups(self):
        # Not stale, because we're using backlinks.
        user_account = yield self.get_user_account()
        group_keys = yield user_account.backlinks.contactgroups(self.manager)
        # NOTE: This assumes that we don't have very large numbers of groups.
        groups = []
        for groups_bunch in self.groups.load_all_bunches(group_keys):
            groups.extend((yield groups_bunch))
        returnValue(sorted(groups, key=lambda group: group.name))

    @Manager.calls_manager
    def contact_has_opted_out(self, contact):
        # FIXME:    opt-outs are currently had coded to only work for msisdns
        if not contact.msisdn:
            return

        user_account = yield self.get_user_account()
        opt_out_store = OptOutStore.from_user_account(user_account)
        opt_out = yield opt_out_store.get_opt_out('msisdn', contact.msisdn)
        returnValue(opt_out)

    def _contact_field_for_addr(self, delivery_class, addr):
        # TODO: change when we have proper address types in vumi
        if delivery_class in ('sms', 'ussd'):
            return {'msisdn': '+' + addr.lstrip('+')}
        elif delivery_class == 'gtalk':
            return {'gtalk_id': addr.partition('/')[0]}
        elif delivery_class == 'twitter':
            return {'twitter_handle': addr}
        else:
            raise ContactError(
                "Unsupported transport_type %r" % delivery_class)

    def new_contact_for_addr(self, delivery_class, addr):
        field = self._contact_field_for_addr(delivery_class, addr)
        field.setdefault('msisdn', u'unknown')
        return self.new_contact(**field)

    @Manager.calls_manager
    def contact_for_addr(self, delivery_class, addr, create=True):
        """
        Returns a contact from a delivery class and address, raising a
        ContactNotFound exception if the contact does not exist.
        """
        field = self._contact_field_for_addr(delivery_class, addr)
        keys = yield self.contacts.search(**field).get_keys()

        if keys:
            returnValue((yield self.contacts.load(keys[0])))

        if create:
            contact_id = uuid4().get_hex()
            field.setdefault('msisdn', u'unknown')
            returnValue(self.contacts(
                contact_id, user_account=self.user_account_key, **field))

        raise ContactNotFoundError(
            "Contact with address '%s' for delivery class '%s' not found."
            % (addr, delivery_class))
