# -*- test-case-name: go.vumitools.tests.test_contact -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import (Unicode, ManyToMany, ForeignKey, Timestamp,
                                    Dynamic)

from go.vumitools.account import UserAccount, PerAccountStore


class ContactGroup(Model):
    """A group of contacts"""
    # key is UUID
    name = Unicode()
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
    extra = Dynamic(prefix='extras-')

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
        else:
            return None

    @classmethod
    def search_group(cls, manager, group, return_keys=False, **kw):
        mr = manager.riak_map_reduce()

        # TODO: populate map/reduce

        if return_keys:
            mapper = lambda manager, result: result.get_key()
        else:
            mapper = lambda manager, result: cls.load(manager,
                                                      result.get_key())
        return manager.run(mr, mapper)

    def __unicode__(self):
        if self.name and self.surname:
            return u' '.join([self.name, self.surname])
        else:
            return self.surname or self.name or u'Unknown User'


class ContactStore(PerAccountStore):
    def setup_proxies(self):
        self.contacts = self.manager.proxy(Contact)
        self.groups = self.manager.proxy(ContactGroup)

    @Manager.calls_manager
    def new_contact(self, **fields):
        contact_id = uuid4().get_hex()

        # These are foreign keys.
        groups = fields.pop('groups', [])

        contact = self.contacts(
            contact_id, user_account=self.user_account_key, **fields)
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

    def get_contact_by_key(self, key):
        return self.contacts.load(key)

    def get_group(self, name):
        return self.groups.load(name)

    def search_group(self, group, return_keys=False, **kw):
        return self.contacts.search_group(self.manager, group,
                                          return_keys=return_keys, **kw)

    @Manager.calls_manager
    def list_contacts(self):
        # Not stale, because we're using backlinks.
        user_account = yield self.get_user_account()
        returnValue(user_account.backlinks.contacts(self.manager))

    @Manager.calls_manager
    def list_groups(self):
        # Not stale, because we're using backlinks.
        user_account = yield self.get_user_account()
        groups = user_account.backlinks.contactgroups(self.manager)
        returnValue(sorted(groups, key=lambda group: group.name))

    @Manager.calls_manager
    def contact_has_opted_out(self, contact):
        # FIXME:    Need to import this to make sure the backlinks are created
        #           even though it isn't used directly.
        from go.vumitools.opt_out import OptOutStore

        # FIXME:    opt-outs are currently had coded to only work for msisdns
        if not contact.msisdn:
            return

        user_account = yield self.get_user_account()
        optouts = yield user_account.backlinks.optouts(manager=contact.manager)
        optout_addrs = [optout.key.split(':', 1)[1] for optout in optouts
                        if optout.key.startswith('msisdn:')]
        returnValue(contact.msisdn in optout_addrs)

    @Manager.calls_manager
    def contact_for_addr(self, delivery_class, addr):
        if delivery_class in ('sms', 'ussd'):
            addr = '+' + addr.lstrip('+')
            contacts = yield self.contacts.search(msisdn=addr)
            if contacts:
                returnValue(contacts[0])
            contact_id = uuid4().get_hex()
            returnValue(self.contacts(contact_id,
                                      user_account=self.user_account_key,
                                      msisdn=addr))
        elif delivery_class == 'gtalk':
            addr = addr.partition('/')[0]
            contacts = yield self.contacts.search(gtalk_id=addr)
            if contacts:
                returnValue(contacts[0])
            contact_id = uuid4().get_hex()
            contact = self.contacts(contact_id,
                                    user_account=self.user_account_key,
                                    gtalk_id=addr, msisdn=u'unknown')
            returnValue(contact)
        else:
            raise RuntimeError("Unsupported transport_type %r"
                               % (delivery_class,))
