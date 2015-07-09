import re

from urllib import urlencode

from django.http import Http404
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from go.contacts.forms import (
    ContactForm, ContactGroupForm, UploadContactsForm, SmartGroupForm,
    SelectContactGroupForm)
from go.contacts import tasks, utils
from go.contacts.import_handlers import (
    handle_import_new_contacts, handle_import_existing_is_truth,
    handle_import_upload_is_truth, ContactImportException)
from go.contacts.parsers import ContactFileParser, ContactParserException
from go.contacts.parsers.base import FieldNormalizer
from go.vumitools.contact import ContactError


def _query_to_kwargs(query):
    pattern = r'(?P<key>[^ :]+):[ ]*(?P<value>[^:]*[^ :])(?:(?=( [^:]+:)|$))'
    tuples = re.findall(pattern, query)
    return dict([(t[0], t[1]) for t in tuples])


def _group_url(group_key):
    return reverse('contacts:group', kwargs={'group_key': group_key})


@login_required
def index(request):
    return redirect(reverse('contacts:groups'))


@login_required
def groups(request, type=None):
    contact_store = request.user_api.contact_store

    if request.POST:
        contact_group_form = ContactGroupForm(request.POST)
        smart_group_form = SmartGroupForm(request.POST)

        if '_new_group' in request.POST:
            if contact_group_form.is_valid():
                group = contact_store.new_group(
                    contact_group_form.cleaned_data['name'])
                messages.add_message(
                    request, messages.INFO, 'New group created')
                return redirect(_group_url(group.key))
        elif '_new_smart_group' in request.POST:
            if smart_group_form.is_valid():
                name = smart_group_form.cleaned_data['name']
                query = smart_group_form.cleaned_data['query']
                smart_group = contact_store.new_smart_group(
                    name, query)
                return redirect(_group_url(smart_group.key))
        elif '_delete' in request.POST:
            groups = request.POST.getlist('group')
            for group_key in groups:
                group = contact_store.get_group(group_key)
                tasks.delete_group.delay(request.user_api.user_account_key,
                                         group.key)
            messages.info(request, '%d groups will be deleted '
                                   'shortly.' % len(groups))
            return redirect(reverse('contacts:groups'))
        elif '_export' in request.POST:
            tasks.export_many_group_contacts.delay(
                request.user_api.user_account_key,
                request.POST.getlist('group'))

            messages.info(request, 'The export is scheduled and should '
                                   'complete within a few minutes.')
            return redirect(reverse('contacts:groups'))
    else:
        contact_group_form = ContactGroupForm()
        smart_group_form = SmartGroupForm()

    user_query = request.GET.get('q', '')
    query = user_query
    if query:
        if ':' not in query:
            query = 'name:%s' % (query,)
        keys = contact_store.groups.raw_search(query).get_keys()
        groups = utils.groups_by_key(contact_store, *keys)
    else:
        if type == 'static':
            groups = contact_store.list_static_groups()
        elif type == 'smart':
            groups = contact_store.list_smart_groups()
        else:
            groups = contact_store.list_groups()

    groups = sorted(groups, key=lambda group: group.created_at, reverse=True)
    paginator = Paginator(groups, 15)
    try:
        page = paginator.page(request.GET.get('p', 1))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    pagination_params = urlencode({
        'query': query,
    })
    return render(request, 'contacts/group_list.html', {
        'paginator': paginator,
        'pagination_params': pagination_params,
        'page': page,
        'query': user_query,
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
    if group.is_smart_group():
        return _smart_group(request, contact_store, group)
    else:
        return _static_group(request, contact_store, group)


def _get_count_and_keys_from_index(index_page, limit):
    count = 0
    keys = []
    while index_page is not None:
        page_keys = list(index_page)
        count += len(page_keys)
        if len(keys) < limit:
            keys.extend(page_keys)
        index_page = index_page.next_page()
    return count, keys[:limit]


@login_required
@csrf_protect
def _static_group(request, contact_store, group):
    if group is None:
        raise Http404

    if request.method == 'POST':
        group_form = ContactGroupForm(request.POST)
        if '_save_group' in request.POST:
            if group_form.is_valid():
                group.name = group_form.cleaned_data['name']
                group.save()
            messages.info(request, 'The group name has been updated')
            return redirect(_group_url(group.key))
        elif '_export' in request.POST:
            tasks.export_group_contacts.delay(
                request.user_api.user_account_key,
                group.key)

            messages.info(request,
                          'The export is scheduled and should '
                          'complete within a few minutes.')
            return redirect(_group_url(group.key))
        elif '_remove' in request.POST:
            contacts = request.POST.getlist('contact')
            for person_key in contacts:
                contact = contact_store.get_contact_by_key(person_key)
                contact.groups.remove(group)
                contact.save()
            messages.info(
                request,
                '%d Contacts removed from group' % len(contacts))
            return redirect(_group_url(group.key))
        elif '_delete_group_contacts' in request.POST:
            tasks.delete_group_contacts.delay(
                request.user_api.user_account_key, group.key)
            messages.info(request,
                          "The group's contacts will be deleted shortly.")
            return redirect(_group_url(group.key))
        elif '_delete_group' in request.POST:
            tasks.delete_group.delay(request.user_api.user_account_key,
                                     group.key)
            messages.info(request, 'The group will be deleted shortly.')
            return redirect(reverse('contacts:index'))
        elif '_complete_contact_upload' in request.POST:
            try:
                import_rule = request.POST.get('import_rule')
                import_handler = {
                    'existing_is_truth': handle_import_existing_is_truth,
                    'upload_is_truth': handle_import_upload_is_truth,
                }.get(import_rule, handle_import_new_contacts)

                import_handler(request, group)
                messages.info(
                    request,
                    'The contacts are being imported. '
                    'We will notify you via email when the import '
                    'has been completed')

            except (ContactParserException, ContactImportException), e:
                if isinstance(e, ContactImportException):
                    error_msg = str(e)
                else:
                    error_msg = 'Something is wrong with the file'
                messages.error(request, error_msg)
                _, file_path = utils.get_file_hints_from_session(request)
                default_storage.delete(file_path)
                utils.clear_file_hints_from_session(request)

            return redirect(_group_url(group.key))

        else:
            upload_contacts_form = UploadContactsForm(request.POST,
                                                      request.FILES)
            if upload_contacts_form.is_valid():
                file_object = upload_contacts_form.cleaned_data['file']
                file_name, file_path = utils.store_temporarily(file_object)
                utils.store_file_hints_in_session(
                    request, file_name, file_path)
                return redirect(_group_url(group.key))
            else:
                # We didn't get any useful POST variables, so just redirect
                # back to the group page without doing anything.
                return redirect(_group_url(group.key))

    else:
        group_form = ContactGroupForm({
            'name': group.name,
        })

    context = {
        'group': group,
        'group_form': group_form,
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
                'field_normalizer': FieldNormalizer(),
                'contact_data_row': row,
                # NOTE: Only if we have a key (contact UUID) value in the
                #       row we can look at updating contacts instead of
                #       only writing new ones.
                'can_update_contacts': 'key' in row,
            })
        except (ValueError, ContactParserException):
            messages.error(request, 'Something is wrong with the file')
            utils.clear_file_hints_from_session(request)
            default_storage.delete(file_path)

    query = request.GET.get('q', '')
    if query:
        if ':' not in query:
            query = 'name:%s' % (query,)
        keys_page = contact_store.search_contacts(query)
    else:
        keys_page = contact_store.get_contact_keys_for_group(group)

    limit = int(request.GET.get('limit', 100))
    count, keys = _get_count_and_keys_from_index(keys_page, limit)
    if keys:
        messages.info(
            request,
            "Showing %s of the group's %s contact(s)" % (len(keys), count))

    contacts = utils.contacts_by_key(contact_store, *keys)
    context.update({
        'query': request.GET.get('q'),
        'selected_contacts': contacts,
        'member_count': contact_store.count_contacts_for_group(group),
    })

    return render(request, 'contacts/static_group_detail.html', context)


@csrf_protect
@login_required
def _smart_group(request, contact_store, group):
    if request.method == 'POST':
        if '_save_group' in request.POST:
            smart_group_form = SmartGroupForm(request.POST)
            if smart_group_form.is_valid():
                group.name = smart_group_form.cleaned_data['name']
                group.query = smart_group_form.cleaned_data['query']
                group.save()
                return redirect(_group_url(group.key))
        elif '_export' in request.POST:
            tasks.export_group_contacts.delay(
                request.user_api.user_account_key, group.key, True)
            messages.info(request, 'The export is scheduled and should '
                                   'complete within a few minutes.')
            return redirect(_group_url(group.key))
        elif '_delete_group_contacts' in request.POST:
            tasks.delete_group_contacts.delay(
                request.user_api.user_account_key, group.key)
            messages.info(
                request, "The group's contacts will be deleted shortly.")
            return redirect(_group_url(group.key))
        elif '_delete_group' in request.POST:
            tasks.delete_group.delay(request.user_api.user_account_key,
                                     group.key)
            messages.info(request, 'The group will be deleted shortly.')
            return redirect(reverse('contacts:index'))
        else:
            # We didn't get any useful POST variables, so just redirect back to
            # the group page without doing anything.
            return redirect(_group_url(group.key))
    else:
        smart_group_form = SmartGroupForm({
            'name': group.name,
            'query': group.query,
        })

    limit = int(request.GET.get('limit', 100))
    keys_page = contact_store.get_contact_keys_for_group(group)
    count, keys = _get_count_and_keys_from_index(keys_page, limit)

    if keys:
        messages.info(
            request,
            "Showing %s of the group's %s contact(s)" % (len(keys), count))

    contacts = utils.contacts_by_key(contact_store, *keys[:limit])
    return render(request, 'contacts/smart_group_detail.html', {
        'group': group,
        'selected_contacts': contacts,
        'group_form': smart_group_form,
    })


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
    upload_contacts_form = None
    group = None

    if request.method == 'POST':
        if '_delete' in request.POST:
            contacts = request.POST.getlist('contact')
            for person_key in contacts:
                contact = contact_store.get_contact_by_key(person_key)
                contact.delete()
            messages.info(request, '%d Contacts deleted' % len(contacts))
        elif '_export' in request.POST:
            tasks.export_contacts.delay(
                request.user_api.user_account_key,
                request.POST.getlist('contact'))
            messages.info(request, 'The export is scheduled and should '
                                   'complete within a few minutes.')
        elif '_export_all' in request.POST:
            tasks.export_all_contacts.delay(
                request.user_api.user_account_key)
            messages.info(request, 'The export is scheduled and should '
                                   'complete within a few minutes.')
        else:
            # first parse the CSV file and create Contact instances
            # from them for attaching to a group later
            upload_contacts_form = UploadContactsForm(
                request.POST, request.FILES)
            if upload_contacts_form.is_valid():
                # We could be creating a new contact group.
                if request.POST.get('name'):
                    new_group_form = ContactGroupForm(request.POST)
                    if new_group_form.is_valid():
                        group = contact_store.new_group(
                            new_group_form.cleaned_data['name'])

                # We could be using an existing contact group.
                elif request.POST.get('contact_group'):
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
                    utils.store_file_hints_in_session(
                        request, file_name, file_path)
                    return redirect(_group_url(group.key))
            else:
                messages.error(
                    request, 'Something went wrong with the upload.')

    select_contact_group_form = SelectContactGroupForm(
        groups=contact_store.list_groups())

    # TODO: A lot of this stuff is duplicated from the similar group search
    #       in the groups() view. We need a function that does that to avoid
    #       the duplication.
    user_query = request.GET.get('q', '')
    query = user_query
    # The _fetch_limit param is mostly for testing, but may be useful as a
    # production hack if we really need to count all contacts or something.
    fetch_limit = int(request.GET.get('_fetch_limit', 10000))
    if query:
        if ':' not in query:
            query = 'name:%s' % (query,)

        # TODO: Use pagination here.
        keys = contact_store.contacts.raw_search(query).get_keys()
    else:
        keys = contact_store.list_contacts_page(max_results=fetch_limit)

    key_count = len(keys)
    limit = min(int(request.GET.get('limit', 100)), key_count)
    # If we have a continuation token, it means there are more than
    # `fetch_limit` keys.
    if getattr(keys, 'continuation', None) is not None:
        key_count = "%s+" % (fetch_limit,)
    messages.info(request, "Showing %s of %s contact(s)" % (limit, key_count))

    smart_group_form = SmartGroupForm(initial={'query': query})
    contacts = utils.contacts_by_key(contact_store, *list(keys)[:limit])

    return render(request, 'contacts/contact_list.html', {
        'query': user_query,
        'selected_contacts': contacts,
        'smart_group_form': smart_group_form,
        'upload_contacts_form': upload_contacts_form or UploadContactsForm(),
        'select_contact_group_form': select_contact_group_form,
    })


@login_required
def person(request, person_key):
    contact_store = request.user_api.contact_store
    try:
        contact = contact_store.get_contact_by_key(person_key)
    except ContactError:
        raise Http404
    groups = contact_store.list_groups()
    if request.method == 'POST':
        if '_delete' in request.POST:
            contact.delete()
            messages.info(request, 'Contact deleted')
            return redirect(reverse('contacts:people'))
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
            'mxit_id': contact.mxit_id,
            'wechat_id': contact.wechat_id,
            'dob': contact.dob,
            'groups': contact.groups.keys(),
        })

    if contact_store.contact_has_opted_out(contact):
        messages.error(request, 'This contact has opted out.')

    return render(request, 'contacts/contact_detail.html', {
        'contact': contact,
        'contact_extra_items': contact.extra.items(),
        'contact_subscription_items': contact.subscription.items(),
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
            messages.add_message(request, messages.INFO, 'Contact created')
            return redirect(reverse('contacts:person', kwargs={
                'person_key': contact.key}))
        else:
            messages.add_message(
                request, messages.ERROR,
                'Please correct the problem below.')
    else:
        form = ContactForm(groups=groups)
    return render(request, 'contacts/contact_detail.html', {
        'form': form,
    })
