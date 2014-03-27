from datetime import datetime

from vumi.persist.model import Model, Manager
from vumi.persist.fields import (Unicode, ManyToMany, ForeignKey, Timestamp,
                                 Dynamic)

from go.vumitools.account.old_models import UserAccountV4


class ContactGroupVNone(Model):
    """A group of contacts"""
    # key is UUID
    name = Unicode()
    query = Unicode(null=True)
    user_account = ForeignKey(UserAccountV4)
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


class ContactVNone(Model):

    """A contact"""
    # key is UUID
    user_account = ForeignKey(UserAccountV4)
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
    groups = ManyToMany(ContactGroupVNone)
    extra = Dynamic(prefix='extras-')
    subscription = Dynamic(prefix='subscription-')

    def add_to_group(self, group):
        if isinstance(group, ContactGroupVNone):
            self.groups.add(group)
        else:
            self.groups.add_key(group)

    def addr_for(self, delivery_class):
        if delivery_class is None:
            # FIXME: Find a better way to do get delivery_class and get rid of
            #        this hack.
            return self.msisdn
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
                    self.gtalk_id or self.twitter_handle or self.msisdn or
                    'Unknown User')
