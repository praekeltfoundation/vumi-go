import redis
from datetime import datetime

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from go.base.utils import make_read_only_form, conversation_or_404
from go.vumitools.api import ConversationSendError
from go.conversation.forms import ConversationForm, ConversationGroupForm

from vxpolls.content import forms
from vxpolls.manager import PollManager


redis = redis.Redis(**settings.VXPOLLS_REDIS_CONFIG)


def get_poll_config(poll_id):
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    config = pm.get_config(poll_id)
    config.update({
        'poll_id': poll_id,
        'transport_name': settings.VXPOLLS_TRANSPORT_NAME,
        'worker_name': settings.VXPOLLS_WORKER_NAME,
    })

    config.setdefault('survey_completed_response',
                        'Thanks for completing the survey')
    return pm, config


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
                u'survey', **conversation_data)
            messages.add_message(request, messages.INFO,
                'Survey Created')
            return redirect(reverse('survey:contents',
                kwargs={'conversation_key': conversation.key}))

    else:
        form = ConversationForm(request.user_api, initial={
            'start_date': datetime.utcnow().date(),
            'start_time': datetime.utcnow().time().replace(second=0,
                                                            microsecond=0),
        })
    return render(request, 'surveys/new.html', {
        'form': form,
    })


@login_required
def contents(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)

    poll_id = 'poll-%s' % (conversation.key,)
    pm, config = get_poll_config(poll_id)
    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data.update({
            'poll_id': poll_id,
            'transport_name': settings.VXPOLLS_TRANSPORT_NAME,
            'worker_name': settings.VXPOLLS_WORKER_NAME,
        })
        form = forms.make_form(data=post_data, initial=config)
        if form.is_valid():
            pm.set(poll_id, form.export())
            if request.POST.get('_save_contents'):
                return redirect(reverse('survey:contents', kwargs={
                    'conversation_key': conversation.key,
                }))
            else:
                return redirect(reverse('survey:people', kwargs={
                    'conversation_key': conversation.key,
                }))
    else:
        form = forms.make_form(data=config, initial=config)

    survey_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.start_timestamp.date(),
            'start_time': conversation.start_timestamp.time(),
        }))
    return render(request, 'surveys/contents.html', {
        'form': form,
        'survey_form': survey_form,
    })


@login_required
def people(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    groups = request.user_api.list_groups()

    poll_id = "poll-%s" % (conversation.key,)
    pm, config = get_poll_config(poll_id)

    if request.method == 'POST':
        if conversation.is_client_initiated():
            try:
                conversation.start()
            except ConversationSendError as error:
                if str(error) == 'No spare messaging tags.':
                    error = 'You have maxed out your available ' \
                            '%(delivery_class)s addresses. ' \
                            'End one or more running %(delivery_class)s ' \
                            'conversations to free one up.' % {
                                'delivery_class': conversation.delivery_class,
                            }
                messages.add_message(request, messages.ERROR, str(error))
                return redirect(reverse('survey:people', kwargs={
                    'conversation_key': conversation.key}))

            addresses = [tag[1] for tag in conversation.get_tags()]
            messages.add_message(request, messages.INFO,
                'Survey started on %s' % (', '.join(addresses),))
            return redirect(reverse('survey:show', kwargs={
                'conversation_key': conversation.key}))
        else:
            group_form = ConversationGroupForm(
                request.POST, groups=request.user_api.list_groups())

            if group_form.is_valid():
                for group in group_form.cleaned_data['groups']:
                    conversation.groups.add_key(group)
                conversation.save()
                messages.add_message(request, messages.INFO,
                    'The selected groups have been added to the survey')
                return redirect(reverse('survey:start', kwargs={
                                    'conversation_key': conversation.key}))

    survey_form = make_read_only_form(ConversationForm(request.user_api))
    content_form = forms.make_form(data=config, initial=config, extra=0)
    read_only_content_form = make_read_only_form(content_form)
    return render(request, 'surveys/people.html', {
        'conversation': conversation,
        'survey_form': survey_form,
        'content_form': read_only_content_form,
        'groups': groups,
    })


@login_required
def start(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        try:
            conversation.start()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('survey:start', kwargs={
                'conversation_key': conversation.key}))
        messages.add_message(request, messages.INFO, 'Survey started')
        return redirect(reverse('survey:show', kwargs={
            'conversation_key': conversation.key}))
    return render(request, 'surveys/start.html', {
        'conversation': conversation,
    })


@login_required
def end(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        conversation.end_conversation()
        messages.add_message(request, messages.INFO, 'Survey ended')
    return redirect(reverse('survey:show', kwargs={
        'conversation_key': conversation.key}))


@login_required
def show(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    poll_id = 'poll-%s' % (conversation.key,)
    return render(request, 'surveys/show.html', {
        'conversation': conversation,
        'poll_id': poll_id,
    })
