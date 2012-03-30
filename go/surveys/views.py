import redis
from datetime import datetime

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from go.conversation.models import Conversation, ConversationSendError
from go.conversation.forms import ConversationForm, SelectDeliveryClassForm
from go.contacts.models import Contact, ContactGroup

from vxpolls.content import forms
from vxpolls.manager import PollManager


redis = redis.Redis(**settings.VXPOLLS_REDIS_CONFIG)

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
            return redirect(reverse('surveys:contents',
                kwargs={'conversation_pk': conversation.pk}))

    else:
        form = ConversationForm(initial={
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
        })
    return render(request, 'surveys/new.html', {
        'form': form,
    })

@login_required
def contents(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    poll_id = 'poll-%s' % (conversation.pk,)

    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    # If this is the first run then load the config
    # from the settings file.
    if poll_id not in pm.polls():
        pm.set(poll_id, settings.VXPOLLS_CONFIG)

    config = pm.get_config(poll_id)
    config.update({
        'poll_id': poll_id,
        'transport_name': settings.VXPOLLS_TRANSPORT_NAME,
    })

    if request.POST:
        post_data = request.POST.copy()
        post_data.update({
            'poll_id': poll_id,
            'transport_name': settings.VXPOLLS_TRANSPORT_NAME,
        })
        form = forms.make_form(data=post_data, initial=config)
        if form.is_valid():
            uid = pm.set(poll_id, form.export())
            print 'saved', poll_id, uid
            print request.POST.get('_save_contents')
            if request.POST.get('_save_contents'):
                return redirect(reverse('surveys:contents', kwargs={
                    'conversation_pk': conversation.pk,
                }))
            else:
                return redirect(reverse('surveys:people', kwargs={
                    'conversation_pk': conversation.pk,
                }))
    else:
        form = forms.make_form(data=config, initial=config)
    return render(request, 'surveys/contents.html', {
        'form': form,
    })

@login_required
def people(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.POST:
        group_pks = request.POST.getlist('groups')
        delivery_class = SelectDeliveryClassForm(request.POST)
        if group_pks and delivery_class.is_valid():
            # get the groups
            groups = ContactGroup.objects.filter(pk__in=group_pks)
            # link to the conversation
            for group in groups:
                conversation.groups.add(group)
            # set the delivery class
            cleaned_data = delivery_class.cleaned_data
            conversation.delivery_class = cleaned_data['delivery_class']
            conversation.save()
            messages.add_message(request, messages.INFO,
                'The selected groups have been added to the survey')
            return redirect(reverse('surveys:start', kwargs={
                'conversation_pk': conversation.pk}))
    return render(request, 'surveys/people.html', {
        'conversation': conversation,
        'delivery_class': SelectDeliveryClassForm(),
    })

@login_required
def start(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.method == 'POST':
        try:
            conversation.start_survey()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('surveys:start', kwargs={
                'conversation_pk': conversation.pk}))
        messages.add_message(request, messages.INFO, 'Survey started')
        return redirect(reverse('surveys:show', kwargs={
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
    return redirect(reverse('surveys:show', kwargs={
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
