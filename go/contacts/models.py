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
    msisdn = models.CharField(blank=False, max_length=255)
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


    def __unicode__(self):
        return u' '.join([self.name, self.surname])
