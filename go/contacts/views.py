import re

from django.http import Http404
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from go.contacts.forms import (
    ContactForm, ContactGroupForm, UploadContactsForm, SmartGroupForm,
    SelectContactGroupForm)
from go.contacts import tasks, utils
from go.contacts.parsers import ContactFileParser, ContactParserException


def _query_to_kwargs(query):
    pattern = r'(?P<key>[^ :]+):[ ]*(?P<value>[^:]*[^ :])(?:(?=( [^:]+:)|$))'
    tuples = re.findall(pattern, query)
    return dict([(t[0], t[1]) for t in tuples])


def _group_url(group_key):
    return reverse('contacts:group', kwargs={'group_key': group_key})


@login_required
def index(request):
    return redirect(reverse('contacts:groups'))


def groups(request):
    contact_store = request.user_api.contact_store
    if request.POST:
        contact_group_form = ContactGroupForm(request.POST)
        smart_group_form = SmartGroupForm(request.POST)

        if '_new_group' in request.POST:
            if contact_group_form.is_valid():
                group = contact_store.new_group(
                    contact_group_form.cleaned_data['name'])
                messages.add_message(request, messages.INFO, 'New group created')
                return redirect(_group_url(group.key))
        elif '_new_smart_group' in request.POST:
            if smart_group_form.is_valid():
                name = smart_group_form.cleaned_data['name']
                query = smart_group_form.cleaned_data['query']
                smart_group = contact_store.new_smart_group(
                    name, query)
                return redirect(_group_url(smart_group.key))
    else:
        contact_group_form = ContactGroupForm()
        smart_group_form = SmartGroupForm()

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
        'contact_group_form': contact_group_form,
    })

@csrf_exempt
def group(request, group_key):
    # the upload handlers can only be set before touching request.POST or
    # request.FILES. The CsrfViewMiddleware touches request.POST, avoid
    # this by doing the CSRF manually with a separate view
    request.upload_handlers = [TemporaryFileUploadHandler()]
    return _group(request, group_key)

@login_required
@csrf_protect
def _group(request, group_key):
    contact_store = request.user_api.contact_store
    group = contact_store.get_group(group_key)
    if group is None:
        raise Http404

    if request.method == 'POST':
        if '_save_group' in request.POST:
            group_form = ContactGroupForm(request.POST)
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
        elif '_complete_contact_upload' in request.POST:
            try:
                file_name, file_path = utils.get_file_hints_from_session(
                    request)
                file_type, parser = ContactFileParser.get_parser(file_name)
                has_header, _, sample_row = parser.guess_headers_and_row(
                    file_path)

                # Grab the selected field names from the submitted form
                # by looping over the expect n number of `column-n` keys being
                # posted
                field_names = [request.POST.get('column-%s' % i) for i in
                                range(len(sample_row))]

                tasks.import_contacts_file.delay(
                    request.user_api.user_account_key, group.key, file_name,
                    file_path, field_names, has_header)

                messages.info(request, 'The contacts are being imported. '
                    'We will notify you via email when the import has '
                    'been completed')

                utils.clear_file_hints_from_session(request)
                return redirect(_group_url(group.key))

            except (ContactParserException,):
                messages.error(request, 'Something is wrong with the file')

        else:
            upload_contacts_form = UploadContactsForm(request.POST,
                                                        request.FILES)
            if upload_contacts_form.is_valid():
                file_object = upload_contacts_form.cleaned_data['file']
                file_name, file_path = utils.store_temporarily(file_object)
                utils.store_file_hints_in_session(request, file_name, file_path)
                return redirect(_group_url(group.key))

    context = {
        'group': group,
    }

    if 'clear-upload' in request.GET:
        # FIXME this is a debug statement
        utils.clear_file_hints_from_session(request)

    if utils.has_uncompleted_contact_import(request):
        try:
            file_name, file_path = utils.get_file_hints_from_session(request)
            file_type, parser = ContactFileParser.get_parser(file_name)
            has_header, headers, row = parser.guess_headers_and_row(file_path)
            context.update({
                'contact_data_headers': headers,
                'contact_data_row': row,
            })
        except (ValueError, ContactParserException):
            messages.error(request, 'Something is wrong with the file')
            utils.clear_file_hints_from_session(request)

    selected_letter = request.GET.get('l', 'a')
    query = request.GET.get('q', '')
    if query:
        if ':' in query:
            query_kwargs = _query_to_kwargs(request.GET.get('q'))
        else:
            query_kwargs = _query_to_kwargs('name:%s' % query)
        selected_contacts = contact_store.contacts.search(**query_kwargs)
    else:
        selected_contacts = contact_store.filter_contacts_on_surname(
            selected_letter, group=group)

    context.update({
        'query': request.GET.get('q'),
        'selected_letter': selected_letter,
        'selected_contacts': selected_contacts,
        })

    return render(request, 'contacts/group.html', context)


@csrf_exempt
def people(request):
    # the upload handlers can only be set before touching request.POST or
    # request.FILES. The CsrfViewMiddleware touches request.POST, avoid
    # this by doing the CSRF manually with a separate view
    request.upload_handlers = [TemporaryFileUploadHandler()]
    return _people(request)

@login_required
@csrf_protect
def _people(request):
    contact_store = request.user_api.contact_store
    group = None

    if request.method == 'POST':
        # first parse the CSV file and create Contact instances
        # from them for attaching to a group later
        upload_contacts_form = UploadContactsForm(request.POST, request.FILES)
        if upload_contacts_form.is_valid():
            # We could be creating a new contact group.
            if request.POST.get('name'):
                new_group_form = ContactGroupForm(request.POST)
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
                file_name, file_path = utils.store_temporarily(file_object)
                utils.store_file_hints_in_session(request, file_name, file_path)
                return redirect(_group_url(group.key))
        else:
            messages.error(request, 'Something went wrong with the upload.')
    else:
        upload_contacts_form = UploadContactsForm()

    select_contact_group_form = SelectContactGroupForm(
        groups=contact_store.list_groups())

    # TODO: A lot of this stuff is duplicated from the similar group search
    #       in the groups() view. We need a function that does that to avoid
    #       the duplication.
    selected_letter = request.GET.get('l', 'a')
    query = request.GET.get('q', '')
    if query:
        if not ':' in query:
			query = 'name:%s' % query
        selected_contacts = contact_store.contacts.riak_search(query)
    else:
        selected_contacts = contact_store.filter_contacts_on_surname(
            selected_letter)

    return render(request, 'contacts/people.html', {
        'query': request.GET.get('q'),
        'selected_letter': selected_letter,
        'selected_contacts': selected_contacts,
        'upload_contacts_form': upload_contacts_form,
        'select_contact_group_form': select_contact_group_form,
        })


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
    })
