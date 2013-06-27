from urllib import urlencode

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages

from go.wizard.forms import (
    Wizard1CreateForm, CampaignBulkMessageForm, CampaignSurveryInitiateForm)
from go.conversation.forms import NewConversationForm
from go.channel.forms import NewChannelForm
from go.base.utils import conversation_or_404


@login_required
def create(request, conversation_key=None):
    """
    TODO: This is a fake implementation, it's not based on anything
    other than displaying the views and perhaps formulating
    some kind of workflow.

    """

    wizard_form = Wizard1CreateForm()
    conversation_form = NewConversationForm()
    channel_form = NewChannelForm(request.user_api)

    conversation = None
    if conversation_key:
        conversation = conversation_or_404(request.user_api, conversation_key)
        conversation_form = NewConversationForm(
            data={'name': conversation.name})

    if request.method == 'POST':
        # TODO: Reuse new conversation view logic here.
        posted_conv_form = NewConversationForm(request.POST)
        if posted_conv_form.is_valid():
            data = posted_conv_form.cleaned_data
            conversation_type = data['conversation_type']
            conversation = request.user_api.new_conversation(
                conversation_type, name=data['name'],
                description=data['description'], config={})
            messages.info(request, 'Conversation created successfully.')

            action = request.POST.get('action')
            if action == 'draft':
                # save and go back to list.
                return redirect('conversations:index')

            # TODO save and go to next step.
            return redirect(
                'wizard:edit', conversation_key=conversation.key)

    return render(request, 'wizard_views/wizard_1_create.html', {
        'wizard_form': wizard_form,
        'conversation_form': conversation_form,
        'channel_form': channel_form,
        'conversation_key': conversation_key,
        'conversation': conversation,
    })


@login_required
def edit(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)

    to = 'wizard:edit_%s' % conversation.conversation_type
    return redirect(to, conversation_key=conversation.key)


@login_required
def edit_survey(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    initiate_form = CampaignSurveryInitiateForm()
    if request.method == 'POST':
        initiate_form = CampaignSurveryInitiateForm(request.POST)
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        # TODO save and go to next step.
        return redirect('wizard:contacts', conversation_key=conversation.key)

    return render(request, 'wizard_views/wizard_2_edit_survey.html', {
        'conversation_key': conversation_key,
        'conversation': conversation,
        'initiate_form': initiate_form
    })


@login_required
def edit_bulk_message(request, conversation_key):
    """The simpler of the two messages."""
    conversation = conversation_or_404(request.user_api, conversation_key)
    form = CampaignBulkMessageForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        # TODO save and go to next step.
        return redirect('wizard:contacts', conversation_key=conversation.key)

    return render(request, 'wizard_views/wizard_2_edit_bulk_message.html', {
        'form': form,
        'conversation': conversation,
        'conversation_key': conversation_key
    })


@login_required
def contacts(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        group_keys = request.POST.getlist('group')

        # TODO: Remove all groups
        for group_key in group_keys:
            conversation.add_group(group_key)
        conversation.save()

        return redirect('conversations:conversation',
                        conversation_key=conversation.key, path_suffix='')

    groups = sorted(request.user_api.list_groups(),
                    key=lambda group: group.created_at,
                    reverse=True)


    contact_store = request.user_api.contact_store
    selected_groups = list(group.key for group in conversation.get_groups())

    for group in groups:
        if group.key in selected_groups:
            group.selected = True

    query = request.GET.get('query', '')
    p = request.GET.get('p', 1)

    paginator = Paginator(groups, 15)
    try:
        page = paginator.page(p)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    pagination_params = urlencode({
        'query': query,
    })

    return render(request, 'wizard_views/wizard_3_contacts.html', {
        'paginator': paginator,
        'page': page,
        'pagination_params': pagination_params,
        'conversation_key': conversation_key,
        'conversation': conversation,
    })


# TODO: Something sensible with the pricing view.
@login_required
def pricing(request):
    return render(request, 'conversations/pricing.html', {
    })
