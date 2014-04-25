import os
import uuid
from datetime import date

from django.core.files.base import File
from django.core.files.storage import default_storage


def store_temporarily(django_file_object):
    django_content_file = File(file=django_file_object,
                               name=django_file_object.name)
    temp_file_name = 'tmp-%s-%s.upload' % (date.today().isoformat(),
                                           uuid.uuid4().hex,)
    temp_file_path = default_storage.save(os.path.join('tmp', temp_file_name),
                                          django_content_file)
    return django_file_object.name, temp_file_path


def store_file_hints_in_session(request, name, path):
    # Not too happy with this method but I don't want to
    # be writing the same session keys everywhere.
    request.session['uploaded_contacts_file_name'] = name
    request.session['uploaded_contacts_file_path'] = path
    return request


def get_file_hints_from_session(request):
    return (request.session['uploaded_contacts_file_name'],
            request.session['uploaded_contacts_file_path'])


def clear_file_hints_from_session(request):
    del request.session['uploaded_contacts_file_name']
    del request.session['uploaded_contacts_file_path']


def has_uncompleted_contact_import(request):
    return 'uploaded_contacts_file_path' in request.session


def contacts_by_key(contact_store, *keys):
    contacts = []
    for bunch in contact_store.contacts.load_all_bunches(keys):
        contacts.extend(bunch)

    return contacts


def groups_by_key(contact_store, *keys):
    groups = []
    for bunch in contact_store.groups.load_all_bunches(keys):
        groups.extend(bunch)

    return groups
