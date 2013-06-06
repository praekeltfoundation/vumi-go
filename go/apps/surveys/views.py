import csv
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
from go.conversation.base import ShowConversationView
from go.conversation.forms import (ConversationForm, ConversationGroupForm,
                                    ReplyToMessageForm)
from go.conversation.tasks import export_conversation_messages
from go.apps.surveys import forms

from vxpolls.manager import PollManager


def get_poll_config(poll_id):
    # FIXME: Do we really need this?
    redis = RedisManager.from_config(settings.VXPOLLS_REDIS_CONFIG)
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    config = pm.get_config(poll_id)
    config.update({
        'poll_id': poll_id,
    })

    config.setdefault('repeatable', True)
    config.setdefault('survey_completed_response',
                        'Thanks for completing the survey')
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
                u'survey', **conversation_data)
            messages.add_message(request, messages.INFO,
                'Survey Created')
            return redirect(reverse('survey:contents',
                kwargs={'conversation_key': conversation.key}))

    else:
        form = ConversationForm(request.user_api)
    return render(request, 'surveys/new.html', {
        'form': form,
    })


def _clear_empties(cleaned_data):
    """
    FIXME:  this is a work around because for some reason Django is seeing
            the new (empty) forms in the formsets as stuff that is to be
            stored when it really should be discarded.
    """
    return [cd for cd in cleaned_data if cd.get('copy')]


@login_required
def contents(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    poll_id = 'poll-%s' % (conversation.key,)
    pm, poll_data = get_poll_config(poll_id)
    questions_data = poll_data.get('questions', [])
    completed_response_data = poll_data.get('survey_completed_responses', [])

    if request.method == 'POST':
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
            if request.POST.get('_save_contents'):
                return redirect(reverse('survey:contents', kwargs={
                    'conversation_key': conversation.key,
                }))
            else:
                return redirect(reverse('survey:people', kwargs={
                    'conversation_key': conversation.key,
                }))
    else:
        poll_form = forms.SurveyPollForm(initial=poll_data)
        questions_formset = forms.make_form_set(initial=questions_data)
        completed_response_formset = forms.make_completed_response_form_set(
            initial=completed_response_data)

    survey_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.created_at.date(),
            'start_time': conversation.created_at.time(),
        }))

    return render(request, 'surveys/contents.html', {
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
    poll_form = forms.SurveyPollForm(initial=poll_data)
    questions_formset = forms.make_form_set(initial=questions_data, extra=0)
    read_only_questions_formset = make_read_only_formset(questions_formset)
    return render(request, 'surveys/people.html', {
        'conversation': conversation,
        'survey_form': survey_form,
        'poll_form': make_read_only_form(poll_form),
        'questions_formset': read_only_questions_formset,
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

    if '_export_conversation_messages' in request.POST:
        export_conversation_messages.delay(
            request.user_api.user_account_key, conversation_key)
        messages.info(request, 'Conversation messages CSV file export '
                                'scheduled. CSV file should arrive in your '
                                'mailbox shortly.')
        return redirect(reverse('survey:show', kwargs={
            'conversation_key': conversation.key,
            }))

    if '_send_one_off_reply' in request.POST:
        form = ReplyToMessageForm(request.POST)
        if form.is_valid():
            in_reply_to = form.cleaned_data['in_reply_to']
            content = form.cleaned_data['content']
            ShowConversationView.send_one_off_reply(
                request.user_api, conversation, in_reply_to, content)
            messages.info(request, 'Reply scheduled for sending.')
            return redirect(reverse('survey:show', kwargs={
                'conversation_key': conversation.key,
                }))
        else:
            messages.error(request,
                'Something went wrong. Please try again.')

    return render(request, 'surveys/show.html', {
        'conversation': conversation,
        'poll_id': poll_id,
    })


@login_required
def edit(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    poll_id = 'poll-%s' % (conversation.key,)
    pm, poll_data = get_poll_config(poll_id)
    questions_data = poll_data.get('questions', [])
    completed_response_data = poll_data.get('survey_completed_responses', [])

    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data.update({
            'poll_id': poll_id,
        })

        questions_formset = forms.make_form_set(data=post_data)
        poll_form = forms.SurveyPollForm(data=post_data)
        completed_response_formset = forms.make_completed_response_form_set(
            data=post_data)
        if (questions_formset.is_valid() and poll_form.is_valid() and
                completed_response_formset.is_valid()):
            data = poll_form.cleaned_data.copy()
            data.update({
                'questions': _clear_empties(questions_formset.cleaned_data),
                'survey_completed_responses': _clear_empties(
                    completed_response_formset.cleaned_data)
                })
            pm.set(poll_id, data)
            messages.info(request, 'Conversation updated.')
            if request.POST.get('_save_contents'):
                return redirect(reverse('survey:edit', kwargs={
                    'conversation_key': conversation.key,
                }))
            else:
                return redirect(reverse('survey:show', kwargs={
                    'conversation_key': conversation.key,
                }))
    else:
        poll_form = forms.SurveyPollForm(initial=poll_data)
        questions_formset = forms.make_form_set(initial=questions_data)
        completed_response_formset = forms.make_completed_response_form_set(
            initial=completed_response_data)

    return render(request, 'surveys/edit.html', {
        'conversation': conversation,
        'poll_form': poll_form,
        'questions_formset': questions_formset,
        'completed_response_formset': completed_response_formset,
    })


@login_required
def download_user_data(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    poll_id = 'poll-%s' % (conversation.key,)
    pm, poll_data = get_poll_config(poll_id)
    poll = pm.get(poll_id)
    csv_data = pm.export_user_data_as_csv(poll)
    return HttpResponse(csv_data, content_type='application/csv')


@login_required
def download_aggregates(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    direction = request.GET.get('direction', 'inbound')
    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerows(conversation.get_aggregate_count(direction))
    return HttpResponse(sio.getvalue(), content_type='text/csv; charset=utf-8')
