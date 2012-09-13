import os.path
import logging

from celery.task import task

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from vumi.persist.fields import ValidationError

from go.vumitools.api import VumiUserApi
from go.base.models import UserProfile
from go.contacts import parsers


@task(ignore_result=True)
def delete_group(account_key, group_key):
    # NOTE: There is a small chance that this can break when running in
    #       production if the load is high and the queues have backed up.
    #       What could happen is that while contacts are being removed from
    #       the group, new contacts could have been added before the group
    #       has been deleted. If this happens those contacts will have
    #       secondary indexes in Riak pointing to a non-existent Group.
    api = VumiUserApi.from_config(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)
    for contact in group.backlinks.contacts():
        contact.groups.remove(group)
        contact.save()
    group.delete()


@task(ignore_result=True)
def import_contacts_file(account_key, group_key, file_type, file_path,
                            field_names, has_header):
    api = VumiUserApi.from_config(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)

    # open in Universal mode to allow us to read files with Windows,
    # MacOS9 & Unix line-endings
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)

    # Get the profile for this user so we can email them when the import
    # has been completed.
    user_profile = UserProfile.objects.get(user_account=account_key)

    count = 0
    written_contacts = []

    parser = {
        'csv': parsers.csv_parser,
    }.get(file_type)

    if parser is None:
        logging.warn('No file parser available for: %s. Stopping' % (
            file_type,))
        return

    try:
        with open(full_path, 'rU') as file_object:
            for data in parser.parse_contacts_file(file_object, field_names,
                                                has_header):
                [count, contact_dictionary] = data

                # Make sure we set this group they're being uploaded in to
                contact_dictionary['groups'] = [group.key]

                contact = contact_store.new_contact(**contact_dictionary)
                written_contacts.append(contact)

        send_mail('Contact import completed successfully.',
            render_to_string('contacts/import_completed_mail.txt', {
                'count': count,
                'group': group,
                'user': user_profile.user,
            }), settings.DEFAULT_FROM_EMAIL, [user_profile.user.email],
            fail_silently=False)

    except (ValueError, ValidationError):
        # Clean up if something went wrong, either everything is written
        # or nothing is written
        for contact in written_contacts:
            contact.delete()

        send_mail('Something went wrong while importing the contacts.',
            render_to_string('contacts/import_failed_mail.txt', {
                'user': user_profile.user,
                'group_key': group_key,
                'account_key': account_key,
                'file_type': file_type,
                'file_path': file_path,
                'field_names': field_names,
                'has_header': has_header,
            }), settings.DEFAULT_FROM_EMAIL, [user_profile.user.email],
            fail_silently=False)
