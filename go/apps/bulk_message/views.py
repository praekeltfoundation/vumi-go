from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.contrib import messages

from go.vumitools.api import ConversationSendError
from go.conversation.forms import ConversationGroupForm
from go.apps.bulk_message.forms import BulkSendConversationForm
from go.base.utils import make_read_only_form, conversation_or_404


@login_required
def new(request):
    if request.POST:
        form = BulkSendConversationForm(request.user_api, request.POST)
        if form.is_valid():
            conversation_data = {}
            copy_keys = [
                'subject',
                'message',
                'delivery_class',
                'delivery_tag_pool',
            ]

            for key in copy_keys:
                conversation_data[key] = form.cleaned_data[key]

            tag_info = form.cleaned_data['delivery_tag_pool'].partition(':')
            conversation_data['delivery_tag_pool'] = tag_info[0]
            if tag_info[2]:
                conversation_data['delivery_tag'] = tag_info[2]

            start_date = form.cleaned_data['start_date'] or datetime.utcnow()
            start_time = (form.cleaned_data['start_time'] or
                            datetime.utcnow().time())
            conversation_data['start_timestamp'] = datetime(
                start_date.year, start_date.month, start_date.day,
                start_time.hour, start_time.minute, start_time.second,
                start_time.microsecond)

            conversation = request.user_api.new_conversation(
                u'bulk_message', **conversation_data)
            messages.add_message(request, messages.INFO,
                'Conversation Created')
            return redirect(reverse('bulk_message:people',
                kwargs={'conversation_key': conversation.key}))
    else:
        form = BulkSendConversationForm(request.user_api, initial={
            'start_date': datetime.utcnow().date(),
            'start_time': datetime.utcnow().time().replace(second=0,
                                                            microsecond=0),
        })

    return render(request, 'bulk_message/new.html', {
        'form': form,
    })


@login_required
def people(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    groups = request.user_api.list_groups()

    if request.method == 'POST':
        group_form = ConversationGroupForm(request.POST, groups=groups)
        if group_form.is_valid():
            for group in group_form.cleaned_data['groups']:
                conversation.groups.add_key(group)
            conversation.save()
            messages.add_message(request, messages.INFO,
                'The selected groups have been added to the conversation')
            return redirect(reverse('bulk_message:send', kwargs={
                'conversation_key': conversation.key}))

    conversation_form = make_read_only_form(BulkSendConversationForm(
            request.user_api, instance=conversation, initial={
                'start_date': conversation.start_timestamp.date(),
                'start_time': conversation.start_timestamp.time(),
                }))
    return render(request, 'bulk_message/people.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'groups': groups,
    })


@login_required
def send(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)

    if request.method == 'POST':
        try:
            conversation.start()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('bulk_message:send', kwargs={
                'conversation_key': conversation.key}))
        messages.add_message(request, messages.INFO, 'Conversation started')
        return redirect(reverse('bulk_message:show', kwargs={
            'conversation_key': conversation.key}))

    conversation_form = make_read_only_form(
        BulkSendConversationForm(
            request.user_api, instance=conversation, initial={
                'start_date': conversation.start_timestamp.date(),
                'start_time': conversation.start_timestamp.time(),
                }))
    groups = request.user_api.list_groups()
    group_form = make_read_only_form(
        ConversationGroupForm(groups=groups))

    return render(request, 'bulk_message/send.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'group_form': group_form,
        'groups': conversation.groups.get_all(),
        'people': conversation.people(),
    })


@login_required
def show(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    return render(request, 'bulk_message/show.html', {
        'conversation': conversation,
    })


@login_required
def end(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        conversation.end_conversation()
        messages.add_message(request, messages.INFO, 'Conversation ended')
    return redirect(reverse('bulk_message:show', kwargs={
        'conversation_key': conversation.key}))
