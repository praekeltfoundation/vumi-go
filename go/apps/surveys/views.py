import redis
from datetime import datetime

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from go.conversation.models import (Conversation, ConversationSendError,
                                    get_combined_delivery_classes)
from go.conversation.forms import (ConversationForm, SelectDeliveryClassForm,
                                    ConversationGroupForm)
from go.contacts.models import ContactGroup
from go.base.utils import make_read_only_form

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
        form = ConversationForm(request.POST)
        if form.is_valid():
            conversation = form.save(commit=False)
            conversation.conversation_type = 'survey'
            conversation.user = request.user
            conversation.save()
            messages.add_message(request, messages.INFO,
                'Survey Created')
            return redirect(reverse('survey:contents',
                kwargs={'conversation_pk': conversation.pk}))

    else:
        form = ConversationForm(initial={
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
        })
    return render(request, 'surveys/new.html', {
        'form': form,
        'delivery_classes': get_combined_delivery_classes(),
    })


@login_required
def contents(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)

    poll_id = 'poll-%s' % (conversation.pk,)
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
                    'conversation_pk': conversation.pk,
                }))
            else:
                return redirect(reverse('survey:people', kwargs={
                    'conversation_pk': conversation.pk,
                }))
    else:
        form = forms.make_form(data=config, initial=config)

    survey_form = make_read_only_form(ConversationForm(instance=conversation))
    return render(request, 'surveys/contents.html', {
        'form': form,
        'survey_form': survey_form,
    })


@login_required
def people(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    groups_for_user = ContactGroup.objects.filter(user=request.user)

    poll_id = "poll-%s" % (conversation.pk,)
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
                    'conversation_pk': conversation.pk}))

            addresses = [tag[1] for tag in conversation.get_tags()]
            messages.add_message(request, messages.INFO,
                'Survey started on %s' % (', '.join(addresses),))
            return redirect(reverse('survey:show', kwargs={
                'conversation_pk': conversation.pk}))
        else:
            group_form = ConversationGroupForm(request.POST,
                                                queryset=groups_for_user)
            group_form.fields['groups'].queryset = groups_for_user

            if group_form.is_valid():
                groups = group_form.cleaned_data['groups']
                group_ids = [grp.pk for grp in groups]
                conversation.groups.add(*group_ids)
                messages.add_message(request, messages.INFO,
                    'The selected groups have been added to the survey')
                return redirect(reverse('survey:start', kwargs={
                                    'conversation_pk': conversation.pk}))

    survey_form = make_read_only_form(ConversationForm(instance=conversation))
    content_form = forms.make_form(data=config, initial=config, extra=0)
    read_only_content_form = make_read_only_form(content_form)
    return render(request, 'surveys/people.html', {
        'conversation': conversation,
        'delivery_class': SelectDeliveryClassForm(),
        'survey_form': survey_form,
        'content_form': read_only_content_form,
    })


@login_required
def start(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.method == 'POST':
        try:
            conversation.start()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('survey:start', kwargs={
                'conversation_pk': conversation.pk}))
        messages.add_message(request, messages.INFO, 'Survey started')
        return redirect(reverse('survey:show', kwargs={
            'conversation_pk': conversation.pk}))
    return render(request, 'surveys/start.html', {
        'conversation': conversation,
    })


@login_required
def end(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.method == 'POST':
        conversation.end_conversation()
        messages.add_message(request, messages.INFO, 'Survey ended')
    return redirect(reverse('survey:show', kwargs={
        'conversation_pk': conversation.pk}))


@login_required
def show(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    poll_id = 'poll-%s' % (conversation.pk,)
    return render(request, 'surveys/show.html', {
        'conversation': conversation,
        'poll_id': poll_id,
    })
