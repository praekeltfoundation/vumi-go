import csv

from django.http import Http404
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings

from vumi.utils import normalize_msisdn

from go.contacts.forms import (
    ContactForm, NewContactGroupForm, UploadContactsForm,
    SelectContactGroupForm)


def _filter_contacts(contacts, request_params):
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


def _create_contacts_from_csv_file(contact_store, csvfile, country_code):
    dialect = csv.Sniffer().sniff(csvfile.read(1024))
    csvfile.seek(0)
    reader = csv.reader(csvfile, dialect=dialect)
    for name, surname, msisdn in reader:
        # TODO: none of these fields are mandatory.
        msisdn = normalize_msisdn(msisdn, country_code=country_code)
        msisdn = unicode(msisdn, 'utf-8')
        name = unicode(name, 'utf-8')
        surname = unicode(surname, 'utf-8')
        contact = contact_store.new_contact(name, surname, msisdn=msisdn)
        yield contact


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

    groups = contact_store.list_groups()
    paginator = Paginator(groups, 5)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'contacts/groups.html', {
        'paginator': paginator,
        'page': page,
        'new_contact_group_form': new_contact_group_form,
        'country_code': settings.VUMI_COUNTRY_CODE,
    })


@login_required
def group(request, group_key):
    contact_store = request.user_api.contact_store
    group = contact_store.get_group(group_key)
    if group is None:
        raise Http404

    if request.method == 'POST':
        upload_contacts_form = UploadContactsForm(request.POST, request.FILES)
        if upload_contacts_form.is_valid():
            try:
                contacts = list(_create_contacts_from_csv_file(
                    contact_store, request.FILES['file'],
                    settings.VUMI_COUNTRY_CODE))

                group.add_contacts(contacts)
                messages.info(request, '%s contacts added' % (len(contacts,)))
                return redirect(_group_url(group.key))
            except ValueError:
                pass

        messages.error(request, 'Something is wrong with the '
                                'file you have uploaded')
    context = {
        'group': group,
        'country_code': settings.VUMI_COUNTRY_CODE,
        }
    context.update(_filter_contacts(group.backlinks.contacts(), request.GET))
    return render(request, 'contacts/group.html', context)


@login_required
def people(request):
    contact_store = request.user_api.contact_store

    if request.method == 'POST':
        # first parse the CSV file and create Contact instances
        # from them for attaching to a group later
        upload_contacts_form = UploadContactsForm(request.POST, request.FILES)
        if upload_contacts_form.is_valid():
            try:
                contacts = _create_contacts_from_csv_file(
                    contact_store, request.FILES['file'],
                    settings.VUMI_COUNTRY_CODE)
                group = None

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

                if group is not None:
                    group.add_contacts(contacts)
                    return redirect(_group_url(group.key))
                else:
                    messages.error(request, 'Please select a group or provide '
                        'a new group name.')
            except UnicodeDecodeError:
                messages.error(request, 'Something went wrong trying to read '
                    'the information from your CSV file. '
                    'Make sure it is saved using the UTF-8 encoding')

        else:
            messages.error(request, 'Something went wrong with the upload.')
    else:
        upload_contacts_form = UploadContactsForm()

    contacts = contact_store.list_contacts()
    context = {
        'upload_contacts_form': upload_contacts_form,
        'contacts': contacts,
        'country_code': settings.VUMI_COUNTRY_CODE,
        }
    context.update(_filter_contacts(contacts, request.GET))
    return render(request, 'contacts/people.html', context)


@login_required
def person(request, person_key):
    contact_store = request.user_api.contact_store
    contact = contact_store.get_contact_by_key(person_key)
    if contact is None:
        raise Http404
    groups = contact_store.list_groups()
    if request.POST:
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
            messages.add_message(request, messages.ERROR,
                'Please correct the problem below.')
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

    return render(request, 'contacts/person.html', {
        'contact': contact,
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
