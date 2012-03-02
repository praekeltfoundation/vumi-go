from django.db import models
import csv


class ContactGroup(models.Model):
    """A group of contacts"""
    user = models.ForeignKey('auth.User')
    name = models.CharField(blank=False, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def add_contacts(self, contacts):
        for contact in contacts:
            self.contact_set.add(contact)

    class Meta:
        ordering = ['-updated_at']
        get_latest_by = 'updated_at'

    def __unicode__(self):
        return self.name


class Contact(models.Model):
    """A contact"""
    user = models.ForeignKey('auth.User')
    name = models.CharField(blank=True, max_length=255)
    surname = models.CharField(blank=True, max_length=255)
    email_address = models.EmailField('Email', blank=True)
    msisdn = models.CharField('Mobile Number', blank=False, max_length=255)
    dob = models.DateField('Date of Birth', help_text='YYYY-MM-DD',
        blank=True, null=True)
    twitter_handle = models.CharField('Twitter Handle', blank=True,
        max_length=100)
    facebook_id = models.CharField('Facebook ID', blank=True, max_length=100)
    bbm_pin = models.CharField('BBM Pin', blank=True, max_length=100)
    gtalk_id = models.EmailField('GTalk ID', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    groups = models.ManyToManyField('contacts.ContactGroup')

    class Meta:
        ordering = ['surname', 'name']
        get_latest_by = 'created_at'

    @classmethod
    def create_from_csv_file(cls, user, csvfile):
        dialect = csv.Sniffer().sniff(csvfile.read(1024))
        csvfile.seek(0)
        reader = csv.reader(csvfile, dialect)
        for name, surname, msisdn in reader:
            # TODO: normalize msisdn
            contact, _ = Contact.objects.get_or_create(user=user,
                msisdn=msisdn)
            contact.name = name
            contact.surname = surname
            contact.save()
            yield contact

    def addr_for(self, transport_type):
        if transport_type == 'sms':
            return self.msisdn
        elif transport_type == 'xmpp':
            return self.gtalk_id
        else:
            return None

    @classmethod
    def for_addr(cls, user, transport_type, addr):
        if transport_type == 'sms':
            addr = '+' + addr.lstrip('+')
            return cls.objects.get(user=user, msisdn=addr)
        elif transport_type == 'xmpp':
            return cls.objects.get(user=user, gtalk_id=addr.partition('/')[0])
        else:
            raise Contact.DoesNotExist("Contact for address %r, transport"
                                       " type %r does not exist."
                                       % (addr, transport_type))

    def __unicode__(self):
        return u' '.join([self.name, self.surname])
