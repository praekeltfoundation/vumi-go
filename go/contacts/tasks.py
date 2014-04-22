import sys
import traceback
from StringIO import StringIO
from zipfile import ZipFile, ZIP_DEFLATED

from celery.task import task

from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from go.vumitools.api import VumiUserApi
from go.vumitools.contact.models import ContactNotFoundError
from go.base.models import UserProfile
from go.base.utils import UnicodeCSVWriter
from go.contacts.parsers import ContactFileParser
from go.contacts.utils import contacts_by_key


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


def zipped_file(filename, data):
    zipio = StringIO()
    zf = ZipFile(zipio, "a", ZIP_DEFLATED)
    zf.writestr(filename, data)
    zf.close()
    return zipio.getvalue()


_contact_fields = [
    'key',
    'name',
    'surname',
    'email_address',
    'msisdn',
    'dob',
    'twitter_handle',
    'facebook_id',
    'bbm_pin',
    'gtalk_id',
    'mxit_id',
    'wechat_id',
    'created_at',
]


def contacts_to_csv(contacts, include_extra=True):
    contacts = sorted(contacts, key=lambda c: c.created_at)

    io = StringIO()
    writer = UnicodeCSVWriter(io)

    # Collect the possible field names for this set of contacts, depending
    # the number of contacts found this could be potentially expensive.
    extra_fields = set()
    if include_extra:
        for contact in contacts:
            extra_fields.update(contact.extra.keys())
    extra_fields = sorted(extra_fields)

    # write the CSV header, prepend extras with `extra-` if it happens to
    # overlap with any of the existing contact's fields.
    writer.writerow(_contact_fields + [
        ('extras-%s' % (f,) if f in _contact_fields else f)
        for f in extra_fields])

    # loop over the contacts and create the row populated with
    # the values of the selected fields.
    for contact in contacts:
        row = [unicode(getattr(contact, field, None) or '')
               for field in _contact_fields]

        if include_extra:
            row.extend([unicode(contact.extra[extra_field] or '')
                        for extra_field in extra_fields])

        writer.writerow(row)

    return io.getvalue()


def get_group_contacts(contact_store, *groups):
    contact_keys = []
    for group in groups:
        contact_keys.extend(contact_store.get_contacts_for_group(group))

    return contacts_by_key(contact_store, *contact_keys)


@task(ignore_result=True)
def export_contacts(account_key, contact_keys, include_extra=True):
    """
    Export a list of contacts as a CSV file and email to the account
    holders' email address.

    :param str account_key:
        The account holders account key
    :param str contact_keys:
        The keys of the contacts to export
    :param bool include_extra:
        Whether or not to include the extra data stored in the dynamic field.
    """

    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store

    contacts = contacts_by_key(contact_store, *contact_keys)
    data = contacts_to_csv(contacts, include_extra)
    file = zipped_file('contacts-export.csv', data)

    # Get the profile for this user so we can email them when the import
    # has been completed.
    user_profile = UserProfile.objects.get(user_account=account_key)

    email = EmailMessage(
        'Contacts export',
        'Please find the CSV data for %s contact(s)' % len(contacts),
        settings.DEFAULT_FROM_EMAIL, [user_profile.user.email])

    email.attach('contacts-export.zip', file, 'application/zip')
    email.send()


@task(ignore_result=True)
def export_all_contacts(account_key, include_extra=True):
    """
    Export all contacts as a CSV file and email to the account
    holders' email address.

    :param str account_key:
        The account holders account key
    :param bool include_extra:
        Whether or not to include the extra data stored in the dynamic field.
    """
    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    contact_keys = contact_store.contacts.all_keys()
    return export_contacts(account_key, contact_keys,
                           include_extra=include_extra)


@task(ignore_result=True)
def export_group_contacts(account_key, group_key, include_extra=True):
    """
    Export a group's contacts as a CSV file and email to the account
    holders' email address.

    :param str account_key:
        The account holders account key
    :param str group_key:
        The group to export contacts for (can be either static or smart groups)
    :param bool include_extra:
        Whether or not to include the extra data stored in the dynamic field.
    """

    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store

    group = contact_store.get_group(group_key)
    contacts = get_group_contacts(contact_store, group)
    data = contacts_to_csv(contacts, include_extra)
    file = zipped_file('contacts-export.csv', data)

    # Get the profile for this user so we can email them when the import
    # has been completed.
    user_profile = UserProfile.objects.get(user_account=account_key)

    email = EmailMessage(
        '%s contacts export' % (group.name,),

        'Please find the CSV data for %s contact(s) from '
        'group "%s" attached.\n\n' % (len(contacts), group.name),

        settings.DEFAULT_FROM_EMAIL, [user_profile.user.email])

    email.attach('contacts-export.zip', file, 'application/zip')
    email.send()


@task(ignore_result=True)
def export_many_group_contacts(account_key, group_keys, include_extra=True):
    """
    Export multiple group contacts as a single CSV file and email to the
    account holders' email address.

    :param str account_key:
        The account holders account key
    :param list group_keys:
        The groups to export contacts for
        (can be either static or smart groups)
    :param bool include_extra:
        Whether or not to include the extra data stored in the dynamic field.
    """

    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store

    groups = [contact_store.get_group(k) for k in group_keys]
    contacts = get_group_contacts(contact_store, *groups)
    data = contacts_to_csv(contacts, include_extra)
    file = zipped_file('contacts-export.csv', data)

    # Get the profile for this user so we can email them when the import
    # has been completed.
    user_profile = UserProfile.objects.get(user_account=account_key)

    email = EmailMessage(
        'Contacts export',

        'Please find the attached CSV data for %s contact(s) from the '
        'following groups:\n%s\n' %
        (len(contacts), '\n'.join('  - %s' % g.name for g in groups)),

        settings.DEFAULT_FROM_EMAIL, [user_profile.user.email])

    email.attach('contacts-export.zip', file, 'application/zip')
    email.send()


@task(ignore_result=True)
def import_new_contacts_file(account_key, group_key, file_name, file_path,
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

        contact_dictionaries = parser.parse_file(file_path, fields, has_header)
        for counter, contact_dictionary in enumerate(contact_dictionaries):

            # Make sure we set this group they're being uploaded in to
            contact_dictionary['groups'] = [group.key]

            contact = contact_store.new_contact(**contact_dictionary)
            written_contacts.append(contact)

        send_mail(
            'Contact import completed successfully.',
            render_to_string('contacts/import_completed_mail.txt', {
                'count': counter,
                'group': group,
                'user': user_profile.user,
            }), settings.DEFAULT_FROM_EMAIL, [user_profile.user.email],
            fail_silently=False)

    except Exception:
        # Clean up if something went wrong, either everything is written
        # or nothing is written
        for contact in written_contacts:
            contact.delete()

        exc_type, exc_value, exc_traceback = sys.exc_info()

        send_mail(
            'Something went wrong while importing the contacts.',
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
    finally:
        default_storage.delete(file_path)


def import_and_update_contacts(contact_mangler, account_key, group_key,
                               file_name, file_path, fields, has_header):
    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    contact_store = api.contact_store
    group = contact_store.get_group(group_key)
    user_profile = UserProfile.objects.get(user_account=account_key)
    extension, parser = ContactFileParser.get_parser(file_name)
    contact_dictionaries = parser.parse_file(file_path, fields, has_header)

    errors = []
    counter = 0

    for contact_dictionary in contact_dictionaries:
        try:
            key = contact_dictionary.pop('key')
            contact = contact_store.get_contact_by_key(key)
            contact_dictionary = contact_mangler(contact, contact_dictionary)
            contact_store.update_contact(key, **contact_dictionary)
            counter += 1
        except KeyError, e:
            errors.append((key, 'No key provided'))
        except ContactNotFoundError, e:
            errors.append((key, str(e)))
        except Exception, e:
            errors.append((key, str(e)))

    email = render_to_string(
        'contacts/import_upload_is_truth_completed_mail.txt', {
            'count': counter,
            'errors': errors,
            'group': group,
            'user': user_profile.user,
        })

    send_mail(
        'Contact import completed.',
        email, settings.DEFAULT_FROM_EMAIL, [user_profile.user.email],
        fail_silently=False)
    default_storage.delete(file_path)


@task(ignore_result=True)
def import_upload_is_truth_contacts_file(account_key, group_key, file_name,
                                         file_path, fields, has_header):

    def merge_operation(contact, contact_dictionary):
        # NOTE:     The order here is important, the new extra is
        #           the truth which we want to maintain
        new_extra = {}
        new_extra.update(dict(contact.extra))
        new_extra.update(contact_dictionary.pop('extra', {}))

        new_subscription = {}
        new_subscription.update(dict(contact.subscription))
        new_subscription.update(contact_dictionary.pop('subscription', {}))

        contact_dictionary['extra'] = new_extra
        contact_dictionary['subscription'] = new_subscription
        contact_dictionary['groups'] = [group_key]
        return contact_dictionary

    return import_and_update_contacts(
        merge_operation, account_key, group_key,
        file_name, file_path,
        fields, has_header)


@task(ignore_result=True)
def import_existing_is_truth_contacts_file(account_key, group_key, file_name,
                                           file_path, fields, has_header):

    def merge_operation(contact, contact_dictionary):
        # NOTE:     The order here is important, the existing extra is
        #           the truth which we want to maintain
        cloned_contact_dictionary = contact_dictionary.copy()
        cloned_contact_dictionary['groups'] = [group_key]

        new_extra = {}
        new_extra.update(contact_dictionary.pop('extra', {}))
        new_extra.update(dict(contact.extra))
        cloned_contact_dictionary['extra'] = new_extra

        new_subscription = {}
        new_subscription.update(contact_dictionary.pop('subscription', {}))
        new_subscription.update(dict(contact.subscription))
        cloned_contact_dictionary['subscription'] = new_subscription

        for key in contact_dictionary.keys():
            # NOTE: If the contact already has any kind of value that
            #       resolves to `True` then skip it.
            #       The current implementation also means that we'll
            #       replace attributes that are empty strings.
            value = getattr(contact, key, None)
            if value:
                cloned_contact_dictionary.pop(key)

        return cloned_contact_dictionary

    return import_and_update_contacts(
        merge_operation, account_key, group_key,
        file_name, file_path,
        fields, has_header)
