from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from go.conversation.models import Conversation
from go.conversation.forms import ConversationForm
from go.base.forms import (NewContactGroupForm, UploadContactsForm,
    SelectContactGroupForm)
from go.base.models import Contact, ContactGroup
from datetime import datetime
import logging


@login_required
def new(request):
    if request.POST:
        form = ConversationForm(request.POST)
        if form.is_valid():
            conversation = form.save(commit=False)
            conversation.user = request.user
            conversation.save()
            return HttpResponseRedirect(reverse('conversation:participants',
                kwargs={'conversation_pk': conversation.pk}))
    else:
        form = ConversationForm(initial={
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M')
        })
    return render(request, 'new.html', {
        'form': form
    })


@login_required
def participants(request, conversation_pk):
    """
    Wow this function is _far_ too big.

    TODO:   This uses too many forms, I think we can combine it into one form
            with a group attribute, in the clean_group() function we can can
            either read the existing group from the db or create a new one
            from the submitted name if it doesn't exist yet.
    """
    conversation = get_object_or_404(Conversation, pk=conversation_pk)
    if request.POST:
        # see if we need to create a new contact group by checking for the name
        if request.POST.getlist('groups'):
            # get the groups
            groups = ContactGroup.objects.filter(
                pk__in=request.POST.getlist('groups'))
            # link to the conversation
            for group in groups:
                conversation.groups.add(group)
            return redirect(reverse('conversation:send', kwargs={
                'conversation_pk': conversation.pk}))

        if request.POST.get('contact_group'):
            new_contact_group_form = NewContactGroupForm()
            select_contact_group_form = SelectContactGroupForm(request.POST)
            if select_contact_group_form.is_valid():
                group = select_contact_group_form.cleaned_data['contact_group']
        elif request.POST.get('name'):
            select_contact_group_form = SelectContactGroupForm()
            new_contact_group_form = NewContactGroupForm(request.POST)
            if new_contact_group_form.is_valid():
                group = new_contact_group_form.save(commit=False)
                group.user = request.user
                group.save()
        else:
            new_contact_group_form = NewContactGroupForm(request.POST)
            select_contact_group_form = SelectContactGroupForm(request.POST)

        # see if we've got a CSV file being uploaded
        if request.FILES.get('file'):
            upload_contacts_form = UploadContactsForm(request.POST,
                request.FILES)
            if upload_contacts_form.is_valid():
                group.import_contacts_from_csv_file(request.FILES['file'])
                conversation.groups.add(group)
                return redirect(reverse('conversation:send', kwargs={
                    'conversation_pk': conversation.pk
                }))
        else:
            upload_contacts_form = UploadContactsForm()
    else:
        upload_contacts_form = UploadContactsForm()
        new_contact_group_form = NewContactGroupForm()
        select_contact_group_form = SelectContactGroupForm()
    return render(request, 'participants.html', {
        'conversation': conversation,
        'select_contact_group_form': select_contact_group_form,
        'new_contact_group_form': new_contact_group_form,
        'upload_contacts_form': upload_contacts_form,
    })


@login_required
def send(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk)
    if request.POST:
        contact_ids = request.POST.getlist('contact')
        contacts = Contact.objects.filter(pk__in=contact_ids)
        for contact in contacts:
            conversation.previewcontacts.add(contact)
        logging.warning('implement sending preview to contacts %s' % contacts)
        return redirect(reverse('conversation:start', kwargs={
            'conversation_pk': conversation.pk}), {
            'contacts': contacts,
        })
    return render(request, 'send.html', {
        'conversation': conversation
    })


@login_required
def start(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk)
    if request.POST:
        return redirect(reverse('conversation:show', kwargs={
            'conversation_pk': conversation.pk}))
    return render(request, 'start.html', {
        'conversation': conversation
    })


@login_required
def show(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk)
    return render(request, 'show.html', {
        'conversation': conversation
    })
