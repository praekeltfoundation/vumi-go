from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from go.base.utils import conversation_or_404
from go.vumitools.api import ConversationSendError
from go.conversation.forms import ConversationForm


@login_required
def new(request):
    if request.POST:
        form = ConversationForm(request.user_api, request.POST)
        if form.is_valid():
            conversation_data = {}
            copy_keys = [
                'subject',
                'message',
                'delivery_class',
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
                u'opt_out', **conversation_data)
            messages.add_message(request, messages.INFO,
                'Opt Out Channel Created')
            return redirect(reverse('opt_out:start',
                kwargs={'conversation_key': conversation.key}))

    else:
        form = ConversationForm(request.user_api, initial={
            'start_date': datetime.utcnow().date(),
            'start_time': datetime.utcnow().time().replace(second=0,
                                                            microsecond=0),
        })
    return render(request, 'opt_out/new.html', {
        'form': form,
    })


@login_required
def start(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        try:
            conversation.start()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('opt_out:start', kwargs={
                'conversation_key': conversation.key}))
        messages.add_message(request, messages.INFO, 'Opt Out channel started')
        return redirect(reverse('opt_out:show', kwargs={
            'conversation_key': conversation.key}))
    return render(request, 'surveys/start.html', {
        'conversation': conversation,
    })


@login_required
def end(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        conversation.end_conversation()
        messages.add_message(request, messages.INFO, 'Opt Out channel ended')
    return redirect(reverse('opt_out:show', kwargs={
        'conversation_key': conversation.key}))


@login_required
def show(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    return render(request, 'opt_out/show.html', {
        'conversation': conversation,
    })
