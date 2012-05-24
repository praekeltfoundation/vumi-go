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


def link_poll_to_conversation(poll_name, poll_id, conversation):
    metadata = conversation.get_metadata(default={})
    vxpolls_metadata = metadata.setdefault('vxpolls', {})
    polls = vxpolls_metadata.setdefault('polls', {})
    polls.update({
        poll_name: poll_id,
    })
    conversation.set_metadata(metadata)
    conversation.save()


def unlink_poll_from_conversation(poll_name, conversation):
    metadata = conversation.get_metadata(default={})
    vxpolls_metadata = metadata.setdefault('vxpolls', {})
    polls = vxpolls_metadata.setdefault('polls', {})
    del polls[poll_name]
    conversation.set_metadata(metadata)
    conversation.save()


def get_polls_for_conversation(conversation):
    metadata = conversation.get_metadata(default={})
    vxpolls_metadata = metadata.setdefault('vxpolls', {})
    return vxpolls_metadata.get('polls', {})


def generate_poll_id(conversation, suffix):
    return 'poll-%s_%s' % (conversation.key, suffix)


def get_poll_config(poll_id):
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    config = pm.get_config(poll_id)
    config.update({
        'poll_id': poll_id,
    })

    # config.setdefault('survey_completed_response',
    #                     'Thanks for completing the survey')
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
                'delivery_tag_pool',
            ]

            for key in copy_keys:
                conversation_data[key] = form.cleaned_data[key]

            start_date = form.cleaned_data['start_date'] or datetime.utcnow()
            start_time = (form.cleaned_data['start_time'] or
                            datetime.utcnow().time())
            conversation_data['start_timestamp'] = datetime(
                start_date.year, start_date.month, start_date.day,
                start_time.hour, start_time.minute, start_time.second,
                start_time.microsecond)

            conversation = request.user_api.new_conversation(
                u'multi_survey', **conversation_data)
            messages.add_message(request, messages.INFO,
                'Survey Created')
            return redirect(reverse('multi_survey:surveys',
                kwargs={'conversation_key': conversation.key}))

    else:
        form = ConversationForm(request.user_api, initial={
            'start_date': datetime.utcnow().date(),
            'start_time': datetime.utcnow().time().replace(second=0,
                                                            microsecond=0),
        })
    return render(request, 'multi_surveys/new.html', {
        'form': form,
    })


@login_required
def surveys(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    polls = get_polls_for_conversation(conversation)

    survey_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.start_timestamp.date(),
            'start_time': conversation.start_timestamp.time(),
        }))

    return render(request, 'multi_surveys/surveys.html', {
        'survey_form': survey_form,
        'conversation': conversation,
        'polls': polls,
    })


@login_required
def new_survey(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    initial_config = {
        'poll_name': '',
    }
    if request.method == 'POST':
        pm = PollManager(redis, settings.VXPOLLS_PREFIX)
        post_data = request.POST.copy()
        form = forms.make_form(data=post_data, initial=initial_config)
        form.fields['poll_name'].required = True
        if form.is_valid():
            poll_name = form.cleaned_data['poll_name']
            poll_id = generate_poll_id(conversation, poll_name)
            link_poll_to_conversation(poll_name, poll_id, conversation)
            pm.set(poll_id, form.export())
            if request.POST.get('_save_contents'):
                return redirect(reverse('multi_survey:survey', kwargs={
                    'conversation_key': conversation.key,
                    'poll_name': poll_name,
                }))
            else:
                return redirect(reverse('multi_survey:surveys', kwargs={
                    'conversation_key': conversation.key,
                }))
    else:
        form = forms.make_form(data=initial_config, initial=initial_config)
        form.fields['poll_name'].required = True

    survey_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.start_timestamp.date(),
            'start_time': conversation.start_timestamp.time(),
        }))
    return render(request, 'multi_surveys/contents.html', {
        'form': form,
        'survey_form': survey_form,
    })


@login_required
def survey(request, conversation_key, poll_name):
    conversation = conversation_or_404(request.user_api, conversation_key)
    poll_id = generate_poll_id(conversation, poll_name)
    pm, config = get_poll_config(poll_id)
    if request.method == 'POST':

        if request.POST.get('_delete_survey'):
            unlink_poll_from_conversation(poll_name, conversation)
            return redirect(reverse('multi_survey:surveys', kwargs={
                'conversation_key': conversation.key,
            }))

        post_data = request.POST.copy()
        post_data.update({
            'poll_id': poll_id,
        })
        form = forms.make_form(data=post_data, initial=config)
        if form.is_valid():
            pm.set(poll_id, form.export())
            link_poll_to_conversation(poll_name, poll_id, conversation)
            if request.POST.get('_save_contents'):
                return redirect(reverse('multi_survey:survey', kwargs={
                    'conversation_key': conversation.key,
                    'poll_name': poll_name,
                }))
            else:
                return redirect(reverse('multi_survey:surveys', kwargs={
                    'conversation_key': conversation.key,
                }))
    else:
        form = forms.make_form(data=config, initial=config)

    survey_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.start_timestamp.date(),
            'start_time': conversation.start_timestamp.time(),
        }))
    return render(request, 'multi_surveys/contents.html', {
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
                return redirect(reverse('multi_survey:people', kwargs={
                    'conversation_key': conversation.key}))

            addresses = [tag[1] for tag in conversation.get_tags()]
            messages.add_message(request, messages.INFO,
                'Survey started on %s' % (', '.join(addresses),))
            return redirect(reverse('multi_survey:show', kwargs={
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
                return redirect(reverse('multi_survey:start', kwargs={
                                    'conversation_key': conversation.key}))

    survey_form = make_read_only_form(ConversationForm(request.user_api))
    content_form = forms.make_form(data=config, initial=config, extra=0)
    read_only_content_form = make_read_only_form(content_form)
    return render(request, 'multi_surveys/people.html', {
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
            return redirect(reverse('multi_survey:start', kwargs={
                'conversation_key': conversation.key}))
        messages.add_message(request, messages.INFO, 'Survey started')
        return redirect(reverse('multi_survey:show', kwargs={
            'conversation_key': conversation.key}))
    return render(request, 'multi_surveys/start.html', {
        'conversation': conversation,
    })


@login_required
def end(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        conversation.end_conversation()
        messages.add_message(request, messages.INFO, 'Survey ended')
    return redirect(reverse('multi_survey:show', kwargs={
        'conversation_key': conversation.key}))


@login_required
def show(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    return render(request, 'multi_surveys/show.html', {
        'conversation': conversation,
    })
