# -*- test-case-name: go.vumitools.tests.test_contact -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import Unicode, ManyToMany, ForeignKey, Timestamp

from go.vumitools.account import UserAccount, PerAccountStore


class ContactGroup(Model):
    """A group of contacts"""
    # key is group name
    user_account = ForeignKey(UserAccount)
    created_at = Timestamp(default=datetime.utcnow)

    @Manager.calls_manager
    def add_contacts(self, contacts, save=True):
        for contact in contacts:
            contact.groups.add(self)
            yield contact.save()

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

    def add_to_group(self, group):
        if isinstance(group, ContactGroup):
            self.groups.add(group)
        else:
            self.groups.add_key(group)

    def addr_for(self, transport_type):
        if transport_type == 'sms':
            return self.msisdn
        elif transport_type == 'xmpp':
            return self.gtalk_id
        else:
            return None

    def __unicode__(self):
        return u' '.join([self.name, self.surname])


class ContactStore(PerAccountStore):
    def setup_proxies(self):
        self.contacts = self.manager.proxy(Contact)
        self.groups = self.manager.proxy(ContactGroup)

    @Manager.calls_manager
    def new_contact(self, name, surname, **fields):
        contact_id = uuid4().get_hex()

        # These are foreign keys.
        groups = fields.pop('groups', [])

        contact = self.contacts(
            contact_id, user_account=self.user_account_key, name=name,
            surname=surname, **fields)
        for group in groups:
            contact.add_to_group(group)

        yield contact.save()
        returnValue(contact)

    @Manager.calls_manager
    def new_group(self, name):
        existing_group = yield self.groups.load(name)
        if existing_group is not None:
            raise ValueError(
                "A group with this name already exists: %s" % (name,))
        group = self.groups(name, user_account=self.user_account_key)
        yield group.save()
        returnValue(group)

    def get_contact_by_key(self, key):
        return self.contacts.load(key)

    def get_group(self, name):
        return self.groups.load(name)

    def list_contacts(self):
        # Not stale, because we're using backlinks.
        return self.user_account.backlinks.contacts(self.manager)

    def list_groups(self):
        # Not stale, because we're using backlinks.
        return self.user_account.backlinks.contactgroups(self.manager)

    @Manager.calls_manager
    def contact_for_addr(self, transport_type, addr):
        if transport_type == 'sms':
            addr = '+' + addr.lstrip('+')
            contacts = yield self.contacts.search(msisdn=addr)
            if contacts:
                returnValue(contacts[0])
            returnValue(self.contacts(user_account=self.user_account_key,
                                      msisdn=addr))
        elif transport_type == 'xmpp':
            addr = addr.partition('/')[0]
            contacts = yield self.contacts.search(gtalk_id=addr)
            if contacts:
                returnValue(contacts[0])
            returnValue(self.contacts(user_account=self.user_account_key,
                                      xmpp=addr))
        else:
            raise RuntimeError("Unsupported transport_type %r"
                               % (transport_type,))
