# -*- test-case-name: go.vumitools.tests.test_contact -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import Unicode, ManyToMany, Timestamp

from go.vumitools.model_store import ModelStore


class ContactGroup(Model):
    """A group of contacts"""
    # key is group name
    # name = Unicode(max_length=255)
    user = Unicode()                    # ForeignKey('auth.User')
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
    user = Unicode()                    # ForeignKey('auth.User')
    name = Unicode(max_length=255, null=True)
    surname = Unicode(max_length=255, null=True)
    email_address = Unicode(null=True)  # EmailField, blank=True
    msisdn = Unicode(max_length=255)    # blank=False
    dob = Timestamp(null=True)
    twitter_handle = Unicode(max_length=100, null=True)
    facebook_id = Unicode(max_length=100, null=True)
    bbm_pin = Unicode(max_length=100, null=True)
    gtalk_id = Unicode(null=True)
    created_at = Timestamp(default=datetime.utcnow)
    groups = ManyToMany(ContactGroup)

    # TODO: Move this elsewhere
    # @classmethod
    # def create_from_csv_file(cls, user, csvfile, country_code):
    #     dialect = csv.Sniffer().sniff(csvfile.read(1024))
    #     csvfile.seek(0)
    #     reader = csv.reader(csvfile, dialect)
    #     for name, surname, msisdn in reader:
    #         # TODO: normalize msisdn
    #         msisdn = normalize_msisdn(msisdn, country_code=country_code)
    #         contact, _ = Contact.objects.get_or_create(user=user,
    #             msisdn=msisdn)
    #         contact.name = name
    #         contact.surname = surname
    #         contact.save()
    #         yield contact

    def addr_for(self, transport_type):
        if transport_type == 'sms':
            return self.msisdn
        elif transport_type == 'xmpp':
            return self.gtalk_id
        else:
            return None

    def __unicode__(self):
        return u' '.join([self.name, self.surname])


class ContactStore(ModelStore):
    def setup_proxies(self):
        self.contacts = self.manager.proxy(Contact)
        self.groups = self.manager.proxy(ContactGroup)

    @Manager.calls_manager
    def new_contact(self, name, surname, **fields):
        contact_id = uuid4().get_hex()
        contact = self.contacts(
            contact_id, user=self.user, name=name, surname=surname,
            created_at=datetime.utcnow(), **fields)
        yield contact.save()
        returnValue(contact)

    @Manager.calls_manager
    def new_group(self, name):
        group = self.groups(name, user=self.user, created_at=datetime.utcnow())
        yield group.save()
        returnValue(group)

    def get_contact_by_key(self, key):
        return self.contacts.load(key)

    def get_group(self, name):
        return self.groups.load(name)

    @Manager.calls_manager
    def contact_for_addr(self, user, transport_type, addr):
        # TODO: Implement this.
        pass
        # if transport_type == 'sms':
        #     addr = '+' + addr.lstrip('+')
        #     return cls.objects.filter(user=user, msisdn=addr).latest()
        # elif transport_type == 'xmpp':
        #     return cls.objects.filter(user=user,
        #             gtalk_id=addr.partition('/')[0]).latest()
        # else:
        #     raise Contact.DoesNotExist("Contact for address %r, transport"
        #                                " type %r does not exist."
        #                                % (addr, transport_type))
