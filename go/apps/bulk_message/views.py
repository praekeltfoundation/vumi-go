from datetime import datetime

from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.conf import settings

from go.vumitools.api import (
    VumiApi, ConversationWrapper, ConversationSendError)
from go.vumitools.contact import ContactStore
from go.vumitools.conversation import (
    ConversationStore, get_server_init_delivery_classes)
from go.conversation.forms import ConversationGroupForm
from go.apps.bulk_message.forms import BulkSendConversationForm
from go.base.utils import make_read_only_form


# TODO: to_addresses in conv.start()

def _conv_or_404(store, key):
    conversation = store.get_conversation_by_key(key)
    if conversation is None:
        raise Http404
    return ConversationWrapper(conversation, VumiApi(settings.VUMI_API_CONFIG))


@login_required
def new(request):
    if request.POST:
        form = BulkSendConversationForm(request.POST)
        if form.is_valid():
            conv_store = ConversationStore.from_django_user(request.user)
            conversation = conv_store.new_conversation(
                u'bulk_message', **form.cleaned_data)
            messages.add_message(request, messages.INFO,
                'Conversation Created')
            return redirect(reverse('bulk_message:people',
                kwargs={'conversation_key': conversation.key}))
    else:
        form = BulkSendConversationForm(initial={
            'start_timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
        })

    return render(request, 'bulk_message/new.html', {
        'form': form,
        'delivery_classes': get_server_init_delivery_classes(),
    })


@login_required
def people(request, conversation_key):
    conv_store = ConversationStore.from_django_user(request.user)
    conversation = _conv_or_404(conv_store, conversation_key)
    contact_store = ContactStore.from_django_user(request.user)
    group_names = [g.key for g in contact_store.list_groups()]

    if request.method == 'POST':
        group_form = ConversationGroupForm(request.POST,
                                           group_names=group_names)
        if group_form.is_valid():
            for group in group_form.cleaned_data['groups']:
                conversation.groups.add_key(group)
            conversation.save()
            messages.add_message(request, messages.INFO,
                'The selected groups have been added to the conversation')
            return redirect(reverse('bulk_message:send', kwargs={
                'conversation_key': conversation.key}))

    conversation_form = make_read_only_form(BulkSendConversationForm())
    group_form = ConversationGroupForm(request.POST, group_names=group_names)
    return render(request, 'bulk_message/people.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'group_form': group_form,
        'delivery_classes': get_server_init_delivery_classes(),
    })


@login_required
def send(request, conversation_key):
    conv_store = ConversationStore.from_django_user(request.user)
    conversation = _conv_or_404(conv_store, conversation_key)

    if request.method == 'POST':
        try:
            conversation.start(
                to_addresses=conversation.get_contacts_addresses())
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('bulk_message:send', kwargs={
                'conversation_key': conversation.key}))
        messages.add_message(request, messages.INFO, 'Conversation started')
        return redirect(reverse('bulk_message:show', kwargs={
            'conversation_key': conversation.key}))

    contact_store = ContactStore.from_django_user(request.user)
    group_names = [g.key for g in contact_store.list_groups()]

    conversation_form = make_read_only_form(BulkSendConversationForm())
    group_form = make_read_only_form(
        ConversationGroupForm(group_names=group_names))

    return render(request, 'bulk_message/send.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'group_form': group_form,
    })


@login_required
def show(request, conversation_key):
    conv_store = ConversationStore.from_django_user(request.user)
    conversation = _conv_or_404(conv_store, conversation_key)
    return render(request, 'bulk_message/show.html', {
        'conversation': conversation,
    })


@login_required
def end(request, conversation_key):
    conv_store = ConversationStore.from_django_user(request.user)
    conversation = _conv_or_404(conv_store, conversation_key)
    if request.method == 'POST':
        conversation.end_conversation()
        messages.add_message(request, messages.INFO, 'Conversation ended')
    return redirect(reverse('bulk_message:show', kwargs={
        'conversation_key': conversation.key}))
