import sys
import traceback
from StringIO import StringIO

from celery.task import task

from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from go.vumitools.api import VumiUserApi
from go.base.models import UserProfile
from go.base.utils import UnicodeCSVWriter
from go.contacts.parsers import ContactFileParser


@task(ignore_result=True)
def delete_group(account_key, group_key):
    # NOTE: There is a small chance that this can break when running in
    #       production if the load is high and the queues have backed up.
    #       What could happen is that while contacts are being removed from
    #       the group, new contacts could have been added before the group
    #       has been deleted. If this happens those contacts will have
    #       secondary indexes in Riak pointing to a non-existent Group.
    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)
    # We do this one at a time because we're already saving them one at a time
    # and the boilerplate for fetching batches without having them all sit in
    # memory is ugly.
    for contact_key in group.backlinks.contacts():
        contact = contact_store.get_contact_by_key(contact_key)
        contact.groups.remove(group)
        contact.save()
    group.delete()


@task(ignore_result=True)
def delete_group_contacts(account_key, group_key):
    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)
    contacts = contact_store.get_contacts_for_group(group)
    # We do this one at a time because we're already saving them one at a time
    # and the boilerplate for fetching batches without having them all sit in
    # memory is ugly.
    for contact_key in contacts:
        contact_store.get_contact_by_key(contact_key).delete()


@task(ignore_result=True)
def export_group_contacts(account_key, group_key, include_extra):
    """
    Export the a groups' contacts as a CSV file and email to the account
    holders' email address.

    :param str account_key:
        The account holder's account key
    :param str group_key:
        The group to export contacts for (can be either static or smart groups)
    :param bool include_extra:
        Whether or not to include the extra data stored in the dynamic field.
    """

    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)
    contact_keys = contact_store.get_contacts_for_group(group)

    # Get the profile for this user so we can email them when the import
    # has been completed.
    user_profile = UserProfile.objects.get(user_account=account_key)

    io = StringIO()
    writer = UnicodeCSVWriter(io)

    contacts = []
    for bunch in contact_store.contacts.load_all_bunches(contact_keys):
        contacts.extend(bunch)

    contacts = sorted(contacts, key=lambda c: c.created_at)

    # collect all names that we can export
    fields = ['name', 'surname', 'email_address', 'msisdn', 'dob',
                    'twitter_handle', 'facebook_id', 'bbm_pin', 'gtalk_id',
                    'created_at']

    # Collect the possible field names for this set of contacts, depending
    # the number of contacts found this could be potentially expensive.
    extra_fields = set()
    if include_extra:
        for contact in contacts:
            extra_fields.update(contact.extra.keys())

    # write the CSV header
    extra_fields = sorted(extra_fields)
    writer.writerow(fields + ['extras-%s' % (key,)
                                    for key in extra_fields])

    # loop over the contacts and create the row populated with
    # the values of the selected fields.
    for contact in contacts:
        row = [unicode(getattr(contact, field, None) or '')
                for field in fields]

        if include_extra:
            row.extend([unicode(contact.extra[extra_field] or '')
                        for extra_field in extra_fields])

        writer.writerow(row)

    email = EmailMessage('%s contacts export' % (group.name,),
            'Please find the CSV data for %s contact(s) from '
            'group "%s" attached.\n\n' % (
            len(contact_keys), group.name),
        settings.DEFAULT_FROM_EMAIL, [user_profile.user.email])
    email.attach('contacts-export.csv', io.getvalue(), 'text/csv')
    email.send()


@task(ignore_result=True)
def import_contacts_file(account_key, group_key, file_name, file_path,
                            fields, has_header):
    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)

    # Get the profile for this user so we can email them when the import
    # has been completed.
    user_profile = UserProfile.objects.get(user_account=account_key)

    written_contacts = []

    try:
        extension, parser = ContactFileParser.get_parser(file_name)

        contact_dictionaries = parser.parse_file(file_path, fields,
            has_header)
        for counter, contact_dictionary in enumerate(contact_dictionaries):

            # Make sure we set this group they're being uploaded in to
            contact_dictionary['groups'] = [group.key]

            contact = contact_store.new_contact(**contact_dictionary)
            written_contacts.append(contact)

        send_mail('Contact import completed successfully.',
            render_to_string('contacts/import_completed_mail.txt', {
                'count': counter,
                'group': group,
                'user': user_profile.user,
            }), settings.DEFAULT_FROM_EMAIL, [user_profile.user.email],
            fail_silently=False)

    except:
        # Clean up if something went wrong, either everything is written
        # or nothing is written
        for contact in written_contacts:
            contact.delete()

        exc_type, exc_value, exc_traceback = sys.exc_info()

        send_mail('Something went wrong while importing the contacts.',
            render_to_string('contacts/import_failed_mail.txt', {
                'user': user_profile.user,
                'group_key': group_key,
                'account_key': account_key,
                'file_name': file_name,
                'file_path': file_path,
                'fields': fields,
                'has_header': has_header,
                'exception_type': exc_type,
                'exception_value': mark_safe(exc_value),
                'exception_traceback': mark_safe(
                    traceback.format_tb(exc_traceback)),
            }), settings.DEFAULT_FROM_EMAIL, [
                user_profile.user.email,
                'support+contact-import@vumi.org',
            ], fail_silently=False)
