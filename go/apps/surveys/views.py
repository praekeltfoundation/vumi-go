from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from go.base.utils import (make_read_only_form, make_read_only_formset,
    conversation_or_404)
from go.vumitools.api import ConversationSendError
from go.conversation.forms import ConversationForm, ConversationGroupForm

from go.apps.surveys.forms import (SurveyForm,
    make_mapping_form_class_for_formset, SurveyQuestionFormSet)
from go.apps.surveys.utils import get_poll_config


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


def _clear_empties(cleaned_data):
    """
    FIXME:  this is a work around because for some reason Django is seeing
            the new (empty) forms in the formsets as stuff that is to be
            stored when it really should be discarded.
    """
    return [cd for cd in cleaned_data if cd.get('copy')]


@login_required
def contents(request, conversation_key):
    poll_id = 'poll-%s' % (conversation_key,)
    pm, poll_data = get_poll_config(poll_id)

    conversation = conversation_or_404(request.user_api, conversation_key)
    conversation_metadata = conversation.get_metadata({})
    survey_metadata = conversation_metadata.setdefault('surveys', {})

    if request.method == 'POST':
        questions_formset = SurveyQuestionFormSet(request.POST)
        survey_form = SurveyForm(request.POST)
        MappingFormClass = make_mapping_form_class_for_formset(questions_formset)
        mapping_form = MappingFormClass(request.POST)
        if (questions_formset.is_valid() and survey_form.is_valid()
                and mapping_form.is_valid()):

            data = survey_form.cleaned_data.copy()
            data.update({
                'questions': _clear_empties(questions_formset.cleaned_data),
                })
            pm.set(poll_id, data)

            # Store the mapping on the conversation as metadata
            survey_metadata.update({
                'mappings': mapping_form.get_mappings(),
                'raw_mappings': mapping_form.cleaned_data.copy(),
                })

            conversation.set_metadata(conversation_metadata)
            conversation.save()

            if request.POST.get('_save_contents'):
                return redirect(reverse('survey:contents', kwargs={
                    'conversation_key': conversation.key,
                }))
            else:
                return redirect(reverse('survey:people', kwargs={
                    'conversation_key': conversation.key,
                }))

    else:
        survey_form = SurveyForm(initial=poll_data)
        questions_formset = SurveyQuestionFormSet(
            initial=poll_data['questions'])

    conversation_form = make_read_only_form(ConversationForm(request.user_api,
        instance=conversation, initial={
            'start_date': conversation.start_timestamp.date(),
            'start_time': conversation.start_timestamp.time(),
        }))

    MappingFormClass = make_mapping_form_class_for_formset(questions_formset)
    mapping_form = MappingFormClass(
        initial=survey_metadata.get('raw_mappings', {}))

    return render(request, 'surveys/contents.html', {
        'conversation_form': conversation_form,
        'survey_form': survey_form,
        'questions_formset': questions_formset,
        'mapping_form': mapping_form,
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

    conversation_form = make_read_only_form(ConversationForm(request.user_api))
    survey_form = SurveyForm(initial=poll_data)
    questions_formset = SurveyQuestionFormSet(initial=questions_data)
    read_only_questions_formset = make_read_only_formset(questions_formset)
    return render(request, 'surveys/people.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'survey_form': make_read_only_form(survey_form),
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
    return render(request, 'surveys/show.html', {
        'conversation': conversation,
        'poll_id': poll_id,
    })
