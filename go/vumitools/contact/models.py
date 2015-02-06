# -*- test-case-name: go.vumitools.tests.test_contact -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue
from vumi.persist.model import Model, Manager
from vumi.persist.fields import (
    Unicode, ManyToMany, ForeignKey, Timestamp, Dynamic)

from go.vumitools.account import UserAccount, PerAccountStore
from go.vumitools.contact.migrations import ContactMigrator
from go.vumitools.opt_out import OptOutStore


DELIVERY_CLASSES = {
    'sms': {
        'field': 'msisdn',
        'label': 'SMS',
    },
    'ussd': {
        'field': 'msisdn',
        'label': 'USSD',
    },
    'gtalk': {
        'field': 'gtalk_id',
        'label': 'Google Talk',
    },
    'mxit': {
        'field': 'mxit_id',
        'label': 'Mxit',
    },
    'wechat': {
        'field': 'wechat_id',
        'label': 'WeChat',
    },
    'twitter': {
        'field': 'twitter_handle',
        'label': 'Twitter',
    },
    'voice': {
        'field': 'msisdn',
        'label': 'Voice',
    },
}


DEFAULT_DELIVERY_CLASS = 'ussd'


class ContactError(Exception):
    """Raised when an error occurs accessing or manipulating a Contact"""


class ContactNotFoundError(ContactError):
    """Raised when a contact is not found"""


def normalize_addr(contact_field, addr):
    if contact_field == 'msisdn':
        addr = '+' + addr.lstrip('+')
    elif contact_field == 'gtalk':
        addr = addr.partition('/')[0]
    return (contact_field, addr)

def contact_field_for_addr(delivery_class, addr):
    # TODO: change when we have proper address types in vumi
    delivery_class_dict = DELIVERY_CLASSES.get(delivery_class, None)
    if delivery_class_dict is None:
        raise ContactError("Unsupported transport_type %r" % delivery_class)

    contact_field = delivery_class_dict['field']
    return contact_field, addr


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

    VERSION = 2
    MIGRATOR = ContactMigrator

    # key is UUID
    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255, null=True)
    surname = Unicode(max_length=255, null=True)
    email_address = Unicode(null=True)  # EmailField?
    dob = Timestamp(null=True)
    created_at = Timestamp(default=datetime.utcnow)
    groups = ManyToMany(ContactGroup)
    extra = Dynamic(prefix='extras-')
    subscription = Dynamic(prefix='subscription-')

    # Address fields
    msisdn = Unicode(max_length=255, index=True)
    twitter_handle = Unicode(max_length=100, null=True, index=True)
    facebook_id = Unicode(max_length=100, null=True, index=True)
    bbm_pin = Unicode(max_length=100, null=True, index=True)
    gtalk_id = Unicode(null=True, index=True)
    mxit_id = Unicode(null=True, index=True)
    wechat_id = Unicode(null=True, index=True)

    ADDRESS_FIELDS = [
        'msisdn', 'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
        'mxit_id', 'wechat_id']

    def add_to_group(self, group):
        if isinstance(group, ContactGroup):
            self.groups.add(group)
        else:
            self.groups.add_key(group)

    def addr_for(self, delivery_class):
        if delivery_class is None:
            # FIXME: Find a better way to do get delivery_class and get rid of
            #        this hack.
            return self.msisdn

        delivery_class = DELIVERY_CLASSES.get(delivery_class)
        if delivery_class is not None:
            return getattr(self, delivery_class['field'])

        return None

    def __unicode__(self):
        if self.name and self.surname:
            return u' '.join([self.name, self.surname])
        else:
            return (self.surname or self.name or
                    self.gtalk_id or self.twitter_handle or self.msisdn or
                    self.mxit_id or self.wechat_id or
                    'Unknown User')


class ContactStore(PerAccountStore):
    NONSETTABLE_CONTACT_FIELDS = ['$VERSION', 'user_account']

    # These two values control how contacts are found based on address.
    # If FIND_BY_INDEX is disabled, search will be used instead of index
    # lookups to find contacts. This will improve performance if contacts have
    # not yet been migrated to version 2.
    # If FIND_BY_INDEX_SEARCH_FALLBACK is disabled, the fallback search (used
    # when the index lookup is enabled and finds nothing) will be disabled.
    # This avoids unnecessary work if the contacts being sought don't exist,
    # but will result in false negatives if there are matching contacts that
    # have not yet been migrated to version 2.
    FIND_BY_INDEX = True
    FIND_BY_INDEX_SEARCH_FALLBACK = False

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

    def get_group(self, key):
        return self.groups.load(key)

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

    def list_contacts(self):
        return self.list_keys(self.contacts)

    @Manager.calls_manager
    def list_groups(self):
        # FIXME: Loading and returning all groups is a potential performance
        #        issue, especially if the caller doesn't need them all.
        group_keys = yield self.list_keys(self.groups)
        # NOTE: This assumes that we don't have very large numbers of groups.
        groups = []
        for groups_bunch in self.groups.load_all_bunches(group_keys):
            groups.extend((yield groups_bunch))
        returnValue(sorted(groups, key=lambda group: group.name))

    @Manager.calls_manager
    def list_smart_groups(self):
        # FIXME: When used with list_static_groups() we load each group twice.
        groups = yield self.list_groups()
        returnValue([group for group in groups if group.is_smart_group()])

    @Manager.calls_manager
    def list_static_groups(self):
        # FIXME: When used with list_smart_groups() we load each group twice.
        groups = yield self.list_groups()
        returnValue([group for group in groups if not group.is_smart_group()])

    @Manager.calls_manager
    def contact_has_opted_out(self, contact):
        # FIXME:    opt-outs are currently had coded to only work for msisdns
        if not contact.msisdn:
            return

        user_account = yield self.get_user_account()
        opt_out_store = OptOutStore.from_user_account(user_account)
        opt_out = yield opt_out_store.get_opt_out('msisdn', contact.msisdn)
        returnValue(opt_out)

    def delivery_class_supported(self, delivery_class):
        """Return True if the delivery class is supported."""
        return delivery_class in DELIVERY_CLASSES

    def new_contact_for_addr(self, delivery_class, addr):
        field, value = contact_field_for_addr(delivery_class, addr)
        field_dict = {field: value}
        field_dict.setdefault('msisdn', u'unknown')
        return self.new_contact(**field_dict)

    @Manager.calls_manager
    def contact_for_addr_field(self, field, value, create=True):
        """
        Returns a contact from a field (address type) and address, raising a
        ContactNotFoundError exception if the contact does not exist.
        """
        field, value = normalize_addr(field, value)
        keys = None
        if self.FIND_BY_INDEX:
            keys = yield self.contacts.index_keys(field, value)
        if (keys is None) or (self.FIND_BY_INDEX_SEARCH_FALLBACK and not keys):
            # Either we didn't try an index lookup (keys is None) or fallback
            # search is enabled and the index lookup found nothing.
            keys = yield self.contacts.search(**{field: value}).get_keys()

        if keys:
            contacts = []
            bunches = yield self.contacts.load_all_bunches(keys)
            for bunch in bunches:
                contacts.extend((yield bunch))
            # All the matches we get back may have been deleted from Riak,
            # if that's the case then just continue and create if that's
            # been requested.
            if contacts:
                returnValue(max(contacts, key=lambda c: c.created_at))

        if create:
            contact_id = uuid4().get_hex()
            field_dict = {field: value}
            field_dict.setdefault('msisdn', u'unknown')
            returnValue(self.contacts(
                contact_id, user_account=self.user_account_key, **field_dict))

        raise ContactNotFoundError(
            "Contact with field '%s' equal to value '%s' not found."
            % (field, value))

    @Manager.calls_manager
    def contact_for_addr(self, delivery_class, addr, create=True):
        """
        Returns a contact from a delivery class and address, raising a
        ContactNotFoundError exception if the contact does not exist.
        """
        field, value = contact_field_for_addr(delivery_class, addr)
        try:
            contact = yield self.contact_for_addr_field(field, value, create)
        except ContactNotFoundError:
            raise ContactNotFoundError(
                "Contact with address '%s' for delivery class '%s' not found."
                % (addr, delivery_class))
        returnValue(contact)
        
