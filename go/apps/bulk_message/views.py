from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.contrib import messages
from go.conversation.models import (Conversation, ConversationSendError,
                                    get_server_init_delivery_classes)
from go.conversation.forms import ConversationGroupForm
from go.apps.bulk_message.forms import BulkSendConversationForm
from go.contacts.models import ContactGroup
from go.base.utils import make_read_only_form
from datetime import datetime


@login_required
def new(request):
    if request.POST:
        form = BulkSendConversationForm(request.POST)
        if form.is_valid():
            conversation = form.save(commit=False)
            conversation.user = request.user
            conversation.save()
            messages.add_message(request, messages.INFO,
                'Conversation Created')
            return redirect(reverse('bulk_message:people',
                kwargs={'conversation_pk': conversation.pk}))
    else:
        form = BulkSendConversationForm(initial={
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
        })

    return render(request, 'bulk_message/new.html', {
        'form': form,
        'delivery_classes': get_server_init_delivery_classes(),
    })


@login_required
def people(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    groups_for_user = ContactGroup.objects.filter(user=request.user)

    if request.method == 'POST':
        group_form = ConversationGroupForm(request.POST,
                                            queryset=groups_for_user)
        if group_form.is_valid():
            groups = group_form.cleaned_data['groups']
            conversation.groups.add(*groups)
            conversation.save()
            messages.add_message(request, messages.INFO,
                'The selected groups have been added to the conversation')
            return redirect(reverse('bulk_message:send', kwargs={
                'conversation_pk': conversation.pk}))

    conversation_form = make_read_only_form(
                            BulkSendConversationForm(instance=conversation))

    group_form = ConversationGroupForm(request.POST, queryset=groups_for_user)
    return render(request, 'bulk_message/people.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'group_form': group_form,
        'delivery_classes': get_server_init_delivery_classes(),
    })


@login_required
def send(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)

    if request.method == 'POST':
        try:
            conversation.send_messages()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('bulk_message:send', kwargs={
                'conversation_pk': conversation.pk}))
        messages.add_message(request, messages.INFO, 'Conversation started')
        return redirect(reverse('bulk_message:show', kwargs={
            'conversation_pk': conversation.pk}))

    conversation_form = make_read_only_form(BulkSendConversationForm(
                                                instance=conversation))
    group_form = make_read_only_form(ConversationGroupForm(
                            queryset=request.user.contactgroup_set.all()))

    return render(request, 'bulk_message/send.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'group_form': group_form,
    })


@login_required
def start(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.method == 'POST':
        try:
            conversation.send_messages()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('bulk_message:start', kwargs={
                'conversation_pk': conversation.pk}))
        messages.add_message(request, messages.INFO, 'Conversation started')
        return redirect(reverse('bulk_message:show', kwargs={
            'conversation_pk': conversation.pk}))
    return render(request, 'bulk_message/start.html', {
        'conversation': conversation,
    })


@login_required
def show(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    return render(request, 'bulk_message/show.html', {
        'conversation': conversation,
    })


@login_required
def end(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.method == 'POST':
        conversation.end_conversation()
        messages.add_message(request, messages.INFO, 'Conversation ended')
    return redirect(reverse('bulk_message:show', kwargs={
        'conversation_pk': conversation.pk}))
