import csv
from datetime import datetime
from StringIO import StringIO

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from vumi.persist.redis_manager import RedisManager

from go.base.utils import (make_read_only_form, make_read_only_formset,
    conversation_or_404)
from go.vumitools.exceptions import ConversationSendError
from go.conversation.forms import (ConversationForm, ConversationGroupForm,
                                   ReplyToMessageForm)
from go.apps.surveys import forms
from go.apps.surveys.views import _clear_empties
from go.conversation.tasks import (export_conversation_messages,
                                    send_one_off_reply)

from vxpolls.manager import PollManager


def link_poll_to_conversation(poll_name, poll_id, conversation):
    config = conversation.get_config()
    vxpolls_config = config.setdefault('vxpolls', {})
    polls = vxpolls_config.setdefault('polls', {})
    polls.update({
        poll_name: poll_id,
    })
    conversation.set_config(config)
    conversation.save()


def unlink_poll_from_conversation(poll_name, conversation):
    config = conversation.get_config()
    vxpolls_config = config.setdefault('vxpolls', {})
    polls = vxpolls_config.setdefault('polls', {})
    del polls[poll_name]
    conversation.set_config(config)
    conversation.save()


def get_polls_for_conversation(conversation):
    metadata = conversation.get_config()
    vxpolls_metadata = metadata.setdefault('vxpolls', {})
    return vxpolls_metadata.get('polls', {})


def generate_poll_id(conversation, suffix):
    return 'poll-%s_%s' % (conversation.key, suffix)


def get_poll_config(poll_id):
    redis = RedisManager.from_config(settings.VXPOLLS_REDIS_CONFIG)
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    config = pm.get_config(poll_id)
    config.update({
        'poll_id': poll_id,
    })
    return pm, config


@login_required
def new(request):
    if request.POST:
        form = ConversationForm(request.user_api, request.POST)
        if form.is_valid():
            conversation_data = {
                'name': form.cleaned_data['subject'],
                'description': form.cleaned_data['message'],
                'delivery_class': form.cleaned_data['delivery_class'],
                'config': {},
                }

            tag_info = form.cleaned_data['delivery_tag_pool'].partition(':')
            conversation_data['delivery_tag_pool'] = tag_info[0]
            if tag_info[2]:
                conversation_data['delivery_tag'] = tag_info[2]

            conversation = request.user_api.new_conversation(
                u'multi_survey', **conversation_data)
            messages.add_message(request, messages.INFO,
                'Survey Created')
            return redirect(reverse('multi_survey:surveys',
                kwargs={'conversation_key': conversation.key}))

    else:
        form = ConversationForm(request.user_api)
    return render(request, 'multi_surveys/new.html', {
        'form': form,
    })


@login_required
def surveys(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    polls = get_polls_for_conversation(conversation)

    survey_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.created_at.date(),
            'start_time': conversation.created_at.time(),
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
        redis = RedisManager.from_config(settings.VXPOLLS_REDIS_CONFIG)
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
            'start_date': conversation.created_at.date(),
            'start_time': conversation.created_at.time(),
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

        questions_formset = forms.make_form_set(data=post_data)
        completed_response_formset = forms.make_completed_response_form_set(
            data=post_data)
        poll_form = forms.SurveyPollForm(data=post_data)
        if (questions_formset.is_valid() and poll_form.is_valid() and
                completed_response_formset.is_valid()):
            data = poll_form.cleaned_data.copy()
            data.update({
                'questions': _clear_empties(questions_formset.cleaned_data),
                'survey_completed_responses': _clear_empties(
                    completed_response_formset.cleaned_data)
                })
            pm.set(poll_id, data)
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
        poll_form = forms.SurveyPollForm(initial=config)
        questions_data = config.get('questions', [])
        completed_response_data = config.get('survey_completed_responses', [])
        questions_formset = forms.make_form_set(initial=questions_data)
        completed_response_formset = forms.make_completed_response_form_set(
            initial=completed_response_data)

    survey_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.created_at.date(),
            'start_time': conversation.created_at.time(),
        }))

    return render(request, 'multi_surveys/contents.html', {
        'poll_form': poll_form,
        'questions_formset': questions_formset,
        'completed_response_formset': completed_response_formset,
        'survey_form': survey_form,
    })


@login_required
def people(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    groups = request.user_api.list_groups()

    poll_id = "poll-%s" % (conversation.key,)
    pm, poll_data = get_poll_config(poll_id)
    questions_data = poll_data.get('questions', [])

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

    survey_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.created_at.date(),
            'start_time': conversation.created_at.time(),
        }))
    content_form = forms.make_form_set(initial=questions_data, extra=0)
    read_only_content_form = make_read_only_formset(content_form)
    return render(request, 'multi_surveys/people.html', {
        'conversation': conversation,
        'survey_form': survey_form,
        'content_form': read_only_content_form,
        'groups': groups,
        'polls': get_polls_for_conversation(conversation),
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

    if '_export_conversation_messages' in request.POST:
        export_conversation_messages.delay(
            request.user_api.user_account_key, conversation_key)
        messages.info(request, 'Conversation messages CSV file export '
                                'scheduled. CSV file should arrive in your '
                                'mailbox shortly.')
        return redirect(reverse('multi_survey:show', kwargs={
            'conversation_key': conversation.key,
            }))

    if '_send_one_off_reply' in request.POST:
        form = ReplyToMessageForm(request.POST)
        if form.is_valid():
            in_reply_to = form.cleaned_data['in_reply_to']
            content = form.cleaned_data['content']
            send_one_off_reply.delay(
                request.user_api.user_account_key, conversation.key,
                in_reply_to, content)
            messages.info(request, 'Reply scheduled for sending.')
            return redirect(reverse('multi_survey:show', kwargs={
                'conversation_key': conversation.key,
                }))
        else:
            messages.error(request,
                'Something went wrong. Please try again.')

    return render(request, 'multi_surveys/show.html', {
        'conversation': conversation,
    })


@login_required
def download_aggregates(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    direction = request.GET.get('direction', 'inbound')
    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerows(conversation.get_aggregate_count(direction))
    return HttpResponse(sio.getvalue(), content_type='text/csv; charset=utf-8')
