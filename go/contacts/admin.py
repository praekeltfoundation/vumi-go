from django.contrib import admin
from go.contacts.models import Contact, ContactGroup

admin.site.register(ContactGroup)
admin.site.register(Contact)
