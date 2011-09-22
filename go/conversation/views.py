from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib import messages
from go.conversation.models import Conversation
from go.conversation.forms import ConversationForm
from go.contacts.forms import (NewContactGroupForm, UploadContactsForm,
    SelectContactGroupForm)
from go.contacts.models import Contact, ContactGroup
from go.base.utils import padded_queryset
from datetime import datetime
import logging


CONVERSATIONS_PER_PAGE = 6


@login_required
def new(request):
    if request.POST:
        form = ConversationForm(request.POST)
        if form.is_valid():
            conversation = form.save(commit=False)
            conversation.user = request.user
            conversation.save()
            messages.add_message(request, messages.INFO,
                'Conversation Created')
            return redirect(reverse('conversations:people',
                kwargs={'conversation_pk': conversation.pk}))

    else:
        form = ConversationForm(initial={
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M')
        })
    return render(request, 'conversation/new.html', {
        'form': form
    })


@login_required
def upload(request, conversation_pk):
    """
    TODO: This view is still too big.
    """
    conversation = get_object_or_404(Conversation, pk=conversation_pk)
    if request.POST:
        # first parse the CSV file and create Contact instances
        # from them for attaching to a group later
        upload_contacts_form = UploadContactsForm(request.POST,
            request.FILES)
        if upload_contacts_form.is_valid():
            contacts = Contact.create_from_csv_file(request.user,
                request.FILES['file'])
            if request.POST.get('name'):
                new_contact_group_form = NewContactGroupForm(request.POST)
                if new_contact_group_form.is_valid():
                    group = new_contact_group_form.save(commit=False)
                    group.user = request.user
                    group.save()
                    group.add_contacts(contacts)
                    conversation.groups.add(group)
                    messages.add_message(request, messages.INFO,
                        'Contacts uploaded to the group and linked '
                        'to the conversation')
                    return redirect(reverse('conversations:send', kwargs={
                        'conversation_pk': conversation.pk
                    }))
                else:
                    select_contact_group_form = SelectContactGroupForm()

            if request.POST.get('contact_group'):
                select_contact_group_form = SelectContactGroupForm(
                    request.POST)
                if select_contact_group_form.is_valid():
                    cleaned_data = select_contact_group_form.cleaned_data
                    group = cleaned_data['contact_group']
                    group.add_contacts(contacts)
                    conversation.groups.add(group)
                    messages.add_message(request, messages.INFO,
                        'Contacts uploaded to the group and linked '
                        'to the conversation')
                    return redirect(reverse('conversations:send', kwargs={
                        'conversation_pk': conversation.pk
                    }))
                else:
                    new_contact_group_form = NewContactGroupForm()
        else:
            new_contact_group_form = NewContactGroupForm()
            select_contact_group_form = SelectContactGroupForm()
            messages.add_message(request, messages.ERROR,
                'Something is wrong with the file you tried to upload.')
    else:
        upload_contacts_form = UploadContactsForm()
        new_contact_group_form = NewContactGroupForm()
        select_contact_group_form = SelectContactGroupForm()

    return render(request, 'conversation/upload.html', {
        'conversation': conversation,
        'upload_contacts_form': upload_contacts_form,
        'new_contact_group_form': new_contact_group_form,
        'select_contact_group_form': select_contact_group_form,
    })


@login_required
def people(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.POST:
        group_pks = request.POST.getlist('groups')
        if group_pks:
            # get the groups
            groups = ContactGroup.objects.filter(pk__in=group_pks)
            # link to the conversation
            for group in groups:
                conversation.groups.add(group)
            messages.add_message(request, messages.INFO, 
                'The selected groups have been added to the conversation')
            return redirect(reverse('conversations:send', kwargs={
                'conversation_pk': conversation.pk}))
    return render(request, 'conversation/people.html', {
        'conversation': conversation,
    })


@login_required
def send(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.POST:
        contact_ids = request.POST.getlist('contact')
        contacts = Contact.objects.filter(pk__in=contact_ids)
        for contact in contacts:
            conversation.previewcontacts.add(contact)
        logging.warning('implement sending preview to contacts %s' % contacts)
        messages.add_message(request, messages.INFO, 'Previews sent')
        return redirect(reverse('conversations:start', kwargs={
            'conversation_pk': conversation.pk}), {
            'contacts': contacts,
        })
    return render(request, 'conversation/send.html', {
        'conversation': conversation
    })


@login_required
def start(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.method == 'POST':
        messages.add_message(request, messages.INFO, 'Conversation started')
        return redirect(reverse('conversations:show', kwargs={
            'conversation_pk': conversation.pk}))
    return render(request, 'conversation/start.html', {
        'conversation': conversation
    })


@login_required
def show(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    return render(request, 'conversation/show.html', {
        'conversation': conversation
    })


@login_required
def index(request):
    conversations = request.user.conversation_set.all()
    query = request.GET.get('q', '')
    if query:
        conversations = conversations.filter(subject__icontains=query)
    if conversations.count() < CONVERSATIONS_PER_PAGE:
        conversations = padded_queryset(conversations, CONVERSATIONS_PER_PAGE)
    paginator = Paginator(conversations, CONVERSATIONS_PER_PAGE)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'conversation/index.html', {
        'conversations': conversations,
        'paginator': paginator,
        'page': page,
        'query': query
    })
