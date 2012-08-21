import csv
import re
import uuid
import os.path
from StringIO import StringIO

from django.http import Http404
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.core.files.base import File
from django.conf import settings
from django.utils.datastructures import SortedDict

from vumi.utils import normalize_msisdn

from go.vumitools.contact import Contact
from go.contacts.forms import (
    ContactForm, NewContactGroupForm, UploadContactsForm,
    SelectContactGroupForm)
from go.contacts import tasks


def _query_to_kwargs(query):
    pattern = r'(?P<key>[^ :]+):[ ]*(?P<value>[^:]*[^ :])(?:(?=( [^:]+:)|$))'
    tuples = re.findall(pattern, query)
    return dict([(t[0], t[1]) for t in tuples])


def _filter_contacts(contacts, request_params):
    contacts = [c for c in contacts if (c.name or c.surname)]
    query = request_params.get('q', None)
    selected_letter = None

    if query:
        ql = query.lower()
        contacts = [c for c in contacts
                    if (ql in c.name.lower()) or (ql in c.surname.lower())]
    else:
        selected_letter = request_params.get('l', 'a').lower()
        contacts = [c for c in contacts
                    if c.surname.lower().startswith(selected_letter)]

    return {
        'query': query,
        'selected_letter': selected_letter,
        'selected_contacts': sorted(contacts,
                                    key=lambda c: c.name.lower()[0]),
        }


def _read_data_from_csv_file(csvfile, field_names):
    dialect = csv.Sniffer().sniff(csvfile.read(1024))
    csvfile.seek(0)
    reader = csv.DictReader(csvfile, field_names, dialect=dialect)
    for row in reader:
        # Only process rows that actually have data
        if any([column for column in row]):
            # Our Riak client requires unicode for all keys & values stored.
            unicoded_row = dict([(key, unicode(value, 'utf-8'))
                                    for key, value in row.items()])
            yield unicoded_row


def _group_url(group_key):
    return reverse('contacts:group', kwargs={'group_key': group_key})


@login_required
def index(request):
    return redirect(reverse('contacts:groups'))


@login_required
def groups(request):
    contact_store = request.user_api.contact_store
    if request.POST:
        new_contact_group_form = NewContactGroupForm(request.POST)
        if new_contact_group_form.is_valid():
            group = contact_store.new_group(
                new_contact_group_form.cleaned_data['name'])
            messages.add_message(request, messages.INFO, 'New group created')
            return redirect(_group_url(group.key))
    else:
        new_contact_group_form = NewContactGroupForm()

    query = request.GET.get('q', None)
    if query:
        query_kwargs = _query_to_kwargs(query)
        if query_kwargs:
            groups = contact_store.groups.search(**query_kwargs)
        else:
            groups = []
    else:
        groups = contact_store.list_groups()

    paginator = Paginator(groups, 5)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'contacts/groups.html', {
        'paginator': paginator,
        'page': page,
        'query': query,
        'new_contact_group_form': new_contact_group_form,
        'country_code': settings.VUMI_COUNTRY_CODE,
    })


def _is_header_row(columns):
    column_set = set([column.lower() for column in columns])
    hint_set = set(['phone', 'contact', 'msisdn', 'number'])
    return hint_set.intersection(column_set)


def _guess_headers_and_row(csv_data):
    sio = StringIO(csv_data)
    dialect = csv.Sniffer().sniff(sio.read(1024))
    sio.seek(0)

    [first_row, second_row] = csv.reader(sio, dialect=dialect)
    default_headers = {
        'name': 'Name',
        'surname': 'Surname',
        'bbm_pin': 'BBM Pin',
        'msisdn': 'Contact Number',
        'gtalk_id': 'GTalk (or XMPP) address',
        'dob': 'Date of Birth',
        'facebook_id': 'Facebook ID',
        'twitter_handle': 'Twitter handle',
        'email_address': 'Email address',
    }

    if _is_header_row(first_row):
        sample_row = SortedDict(zip(first_row, second_row))
        for column in first_row:
            default_headers.setdefault(column, column)
        return True, default_headers, sample_row
    return (False, default_headers,
        SortedDict([(column, None) for column in first_row]))


def _get_file_hints(content_file):
    # Save the file object temporarily so we can present
    # some UI to help the user figure out which columns are
    # what of what type.
    temp_file_name = '%s.csv' % (uuid.uuid4().hex,)
    django_content_file = File(file=content_file, name=temp_file_name)
    temp_file_path = default_storage.save(os.path.join('tmp', temp_file_name),
        django_content_file)
    # Store the first two lines in the session, we'll present these
    # in the UI on the following page to help the user determine
    # which column represents what.
    content_file.seek(0)
    first_two_lines = '\n'.join([
        content_file.readline().strip() for i in range(2)])

    return temp_file_path, first_two_lines


def _store_file_hints_in_session(request, path, data):
    # Not too happy with this method but I don't want to
    # be writing the same session keys everywhere.
    request.session['uploaded_csv_path'] = path
    request.session['uploaded_csv_data'] = data
    return request


def _get_file_hints_from_session(request):
    return [
        request.session['uploaded_csv_path'],
        request.session['uploaded_csv_data'],
    ]


def _clear_file_hints_from_session(request):
    del request.session['uploaded_csv_data']
    del request.session['uploaded_csv_path']


def _has_uncompleted_csv_import(request):
    return (('uploaded_csv_data' in request.session)
        and ('uploaded_csv_path' in request.session))


def _import_csv_file(group, csv_path, field_names, has_header):
    full_path = os.path.join(settings.MEDIA_ROOT, csv_path)
    # open in Universal mode to allow us to reed files with Windows,
    # MacOS9 & Unix line-endings
    csv_file = open(full_path, 'rU')
    data_dictionaries = _read_data_from_csv_file(csv_file,
                                field_names)

    # We need to know what we cannot set to avoid a
    # CSV import overwriting things like account details.
    excluded_attributes = ['user_account',
                            'created_at',
                            'extra']

    known_attributes = [attribute
        for attribute in Contact.field_descriptors.keys()
        if attribute not in excluded_attributes]

    # It's a generator so loop over it and save as contacts
    # in the contact_store, normalizing anything we need to
    for counter, data_dictionary in enumerate(data_dictionaries):

        # If we've determined that the first line of the file is
        # a header then skip it.
        if has_header and counter == 0:
            continue

        # Make sure we set this group they're being uploaded in to
        groups = data_dictionary.setdefault('groups', [])
        groups.append(group.key)

        # Make sure we normalize the msisdn before saving in the db
        if 'msisdn' in data_dictionary:
            msisdn = data_dictionary['msisdn']
            # TODO: fix normalization, Vumi Go won't be bound to a single
            #       country code which can be used for normalization.
            normalized_msisdn = normalize_msisdn(msisdn,
                country_code=settings.VUMI_COUNTRY_CODE)
            data_dictionary.update({
                'msisdn': unicode(normalized_msisdn, 'utf-8')
            })

        # Populate this with whatever we'll be sending to the
        # contact to be saved
        contact_dictionary = {}
        for key, value in data_dictionary.items():
            if key in known_attributes:
                contact_dictionary[key] = value
            else:
                extra = contact_dictionary.setdefault('extra', {})
                extra[key] = value

        yield (counter if has_header else counter + 1, contact_dictionary)


@login_required
def group(request, group_key):
    # Force all CSV uploads to be streamed to disk so we can inspect
    # the file contents for things like windows style \r\n line endings
    request.upload_handlers = [TemporaryFileUploadHandler()]
    contact_store = request.user_api.contact_store
    group = contact_store.get_group(group_key)
    if group is None:
        raise Http404

    if request.method == 'POST':
        if '_save_group' in request.POST:
            group_form = NewContactGroupForm(request.POST)
            if group_form.is_valid():
                group.name = group_form.cleaned_data['name']
                group.save()
            messages.info(request, 'The group name has been updated')
            return redirect(_group_url(group.key))
        elif '_delete_group' in request.POST:
            tasks.delete_group(request.user_api.user_account_key,
                group.key)
            messages.info(request, 'The group will be deleted shortly.')
            return redirect(reverse('contacts:index'))
        elif '_complete_csv_upload' in request.POST:
            try:
                csv_path, csv_data = _get_file_hints_from_session(request)
                has_header, _, sample_row = _guess_headers_and_row(csv_data)

                # Grab the selected field names from the submitted form
                # by looping over the expect n number of `column-n` keys being
                # posted
                field_names = [request.POST.get('column-%s' % i) for i in
                                range(len(sample_row))]

                for csv_data in _import_csv_file(group, csv_path, field_names,
                                                    has_header):
                    [count, contact_dictionary] = csv_data
                    contact_store.new_contact(**contact_dictionary)

                messages.info(request,
                    'Success! %s contacts imported.' % (
                        count,))

                _clear_file_hints_from_session(request)
                return redirect(_group_url(group.key))

            except ValueError:
                messages.error(request, 'Something is wrong with the file')

        else:
            upload_contacts_form = UploadContactsForm(request.POST,
                                                        request.FILES)
            if upload_contacts_form.is_valid():
                file_object = upload_contacts_form.cleaned_data['file']
                _store_file_hints_in_session(request,
                    *_get_file_hints(file_object))
                return redirect(_group_url(group.key))

    context = {
        'group': group,
        'country_code': settings.VUMI_COUNTRY_CODE,
    }

    if 'clear-upload' in request.GET:
        # FIXME this is a debug statement
        del request.session['uploaded_csv_data']

    if _has_uncompleted_csv_import(request):
        try:
            csv_path, csv_data = _get_file_hints_from_session(request)
            has_header, headers, row = _guess_headers_and_row(csv_data)
            context.update({
                'csv_data_headers': headers,
                'csv_data_row': row,
            })
        except ValueError:
            messages.error(request, 'Something is wrong with the file')

    if ':' in request.GET.get('q', ''):
        query = request.GET['q']
        query_kwargs = _query_to_kwargs(query)
        context.update({
            'query': query,
            'selected_contacts': [contact for contact in
                            contact_store.contacts.search(**query_kwargs)],
        })
    else:
        context.update(_filter_contacts(group.backlinks.contacts(),
                                            request.GET))
    return render(request, 'contacts/group.html', context)


@login_required
def people(request):
    # Force all CSV uploads to be streamed to disk so we can inspect
    # the file contents for things like windows style \r\n line endings
    request.upload_handlers = [TemporaryFileUploadHandler()]
    contact_store = request.user_api.contact_store
    if request.method == 'POST':
        # first parse the CSV file and create Contact instances
        # from them for attaching to a group later
        upload_contacts_form = UploadContactsForm(request.POST, request.FILES)
        if upload_contacts_form.is_valid():
            # We could be creating a new contact group.
            if request.POST.get('name'):
                new_group_form = NewContactGroupForm(request.POST)
                if new_group_form.is_valid():
                    group = contact_store.new_group(
                        new_group_form.cleaned_data['name'])

            # We could be using an existing contact group.
            if request.POST.get('contact_group'):
                select_group_form = SelectContactGroupForm(
                    request.POST, groups=contact_store.list_groups())
                if select_group_form.is_valid():
                    group = contact_store.get_group(
                        select_group_form.cleaned_data['contact_group'])

            if group is None:
                messages.error(request, 'Please select a group or provide '
                    'a new group name.')
            else:
                file_object = upload_contacts_form.cleaned_data['file']
                # re-open the file in Universal mode to prevent files
                # with windows line endings spewing errors
                with open(file_object.temporary_file_path(), 'rU') as fp:
                    _store_file_hints_in_session(request,
                        *_get_file_hints(fp))
                return redirect(_group_url(group.key))
        else:
            messages.error(request, 'Something went wrong with the upload.')
    else:
        upload_contacts_form = UploadContactsForm()

    select_contact_group_form = SelectContactGroupForm(
        groups=contact_store.list_groups())
    contacts = contact_store.list_contacts()
    context = {
        'upload_contacts_form': upload_contacts_form,
        'contacts': contacts,
        'country_code': settings.VUMI_COUNTRY_CODE,
        'select_contact_group_form': select_contact_group_form,
        }

    if ':' in request.GET.get('q', ''):
        query = request.GET['q']
        query_kwargs = _query_to_kwargs(query)
        context.update({
            'query': query,
            'selected_contacts': [contact for contact in
                            contact_store.contacts.search(**query_kwargs)],
        })
    else:
        context.update(_filter_contacts(contacts, request.GET))
    return render(request, 'contacts/people.html', context)


@login_required
def person(request, person_key):
    contact_store = request.user_api.contact_store
    contact = contact_store.get_contact_by_key(person_key)
    if contact is None:
        raise Http404
    groups = contact_store.list_groups()
    if request.method == 'POST':
        if '_delete_contact' in request.POST:
            contact.delete()
            messages.info(request, 'Contact deleted')
            return redirect(reverse('contacts:index'))
        else:
            form = ContactForm(request.POST, groups=groups)
            if form.is_valid():
                for k, v in form.cleaned_data.items():
                    if k == 'groups':
                        contact.groups.clear()
                        for group in v:
                            contact.add_to_group(group)
                        continue
                    setattr(contact, k, v)
                contact.save()
                messages.add_message(request, messages.INFO, 'Profile Updated')
                return redirect(reverse('contacts:person', kwargs={
                    'person_key': contact.key}))
            else:
                messages.error(request, 'Please correct the problem below.')
    else:
        form = ContactForm(groups=groups, initial={
            'name': contact.name,
            'surname': contact.surname,
            'email_address': contact.email_address,
            'msisdn': contact.msisdn,
            'twitter_handle': contact.twitter_handle,
            'facebook_id': contact.facebook_id,
            'bbm_pin': contact.bbm_pin,
            'gtalk_id': contact.gtalk_id,
            'dob': contact.dob,
            'groups': [group.key for group in contact.groups.get_all()],
        })

    if contact_store.contact_has_opted_out(contact):
        messages.error(request, 'This contact has opted out.')

    return render(request, 'contacts/person.html', {
        'contact': contact,
        'contact_extra_items': contact.extra.items(),
        'form': form,
        'country_code': settings.VUMI_COUNTRY_CODE,
    })


@login_required
def new_person(request):
    contact_store = request.user_api.contact_store
    groups = contact_store.list_groups()
    if request.POST:
        form = ContactForm(request.POST, groups=groups)
        if form.is_valid():
            contact = contact_store.new_contact(**form.cleaned_data)
            messages.add_message(request, messages.INFO, 'Profile Created')
            return redirect(reverse('contacts:person', kwargs={
                'person_key': contact.key}))
        else:
            messages.add_message(request, messages.ERROR,
                'Please correct the problem below.')
    else:
        form = ContactForm(groups=groups)
    return render(request, 'contacts/new_person.html', {
        'form': form,
        'country_code': settings.VUMI_COUNTRY_CODE,
    })
