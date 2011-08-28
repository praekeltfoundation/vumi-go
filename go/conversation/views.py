from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from go.conversation.models import Conversation
from go.conversation.forms import ConversationForm
from go.base.forms import (NewContactGroupForm, UploadContactsForm, 
    SelectContactGroupForm)
from go.base.models import ContactGroup
from datetime import datetime
from StringIO import StringIO
import csv

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
    conversation = get_object_or_404(Conversation, pk=conversation_pk)
    if request.POST:
        # see if we need to create a new contact group by checking for the name
        if request.POST.get('name'):
            select_contact_group_form = SelectContactGroupForm()
            new_contact_group_form = NewContactGroupForm(request.POST)
            if new_contact_group_form.is_valid():
                group = new_contact_group_form.save(commit=False)
                group.user = request.user
                group.save()
            else:
                print new_contact_group_form.errors
        else:
            new_contact_group_form = NewContactGroupForm()
            select_contact_group_form = SelectContactGroupForm(request.POST)
            if select_contact_group_form.is_valid():
                group = select_contact_group_form.contact_group
            else:
                print select_contact_group_form.errors
        
        # see if we've got a CSV file being uploaded
        if request.FILES.get('file'):
            upload_contacts_form = UploadContactsForm(request.POST, request.FILES)
            if upload_contacts_form.is_valid():
                group.import_contacts_from_csv_file(request.FILES['file'])
            else:
                print upload_contacts_form.errors
        else:
            upload_contacts_form = UploadContactsForm()
    else:
        upload_contacts_form = UploadContactsForm()
        new_contact_group_form = NewContactGroupForm()
    return render(request, 'participants.html', {
        'conversation': conversation,
        'new_contact_group_form': new_contact_group_form,
        'upload_contacts_form': upload_contacts_form,
    })

