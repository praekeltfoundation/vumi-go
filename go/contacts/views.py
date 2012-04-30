import csv

from django.http import Http404
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings

from vumi.utils import normalize_msisdn

from go.vumitools.contact import ContactStore
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
        'selected_contacts': contacts,
        }


def _unicode_csv_reader(unicode_csv_data, dialect, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(_utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]


def _utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')


def _create_contacts_from_csv_file(contact_store, csvfile, country_code):
    dialect = csv.Sniffer().sniff(csvfile.read(1024))
    csvfile.seek(0)
    reader = _unicode_csv_reader(csvfile, dialect)
    for name, surname, msisdn in reader:
        # TODO: normalize msisdn (?)
        msisdn = normalize_msisdn(msisdn, country_code=country_code)
        msisdn = unicode(msisdn, 'utf-8')
        contact = contact_store.new_contact(name, surname, msisdn=msisdn)
        yield contact


def _group_url(group_key):
    return reverse('contacts:group', kwargs={'group_key': group_key})


@login_required
def index(request):
    return redirect(reverse('contacts:groups'))


@login_required
def groups(request):
    contact_store = ContactStore.from_django_user(request.user)
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
    group = ContactStore.from_django_user(request.user).get_group(group_key)
    if group is None:
        raise Http404

    context = {
        'group': group,
        'country_code': settings.VUMI_COUNTRY_CODE,
        }
    context.update(_filter_contacts(group.backlinks.contacts(), request.GET))
    return render(request, 'contacts/group.html', context)


@login_required
def people(request):
    contact_store = ContactStore.from_django_user(request.user)

    # TODO: Error handling in here.

    if request.POST:
        # first parse the CSV file and create Contact instances
        # from them for attaching to a group later
        upload_contacts_form = UploadContactsForm(request.POST, request.FILES)
        if upload_contacts_form.is_valid():
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
            messages.add_message(request, messages.ERROR,
                'Something went wrong with the upload.')

    contacts = contact_store.list_contacts()
    context = {
        'contacts': contacts,
        'country_code': settings.VUMI_COUNTRY_CODE,
        }
    context.update(_filter_contacts(contacts, request.GET))
    return render(request, 'contacts/people.html', context)


@login_required
def person(request, person_key):
    contact_store = ContactStore.from_django_user(request.user)
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
        form = ContactForm(groups=groups)
    return render(request, 'contacts/person.html', {
        'contact': contact,
        'form': form,
        'country_code': settings.VUMI_COUNTRY_CODE,
    })


@login_required
def new_person(request):
    contact_store = ContactStore.from_django_user(request.user)
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
