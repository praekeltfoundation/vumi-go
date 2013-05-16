from urllib import urlencode

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages

from go.campaigns.forms import (
    CampaignGeneralForm, CampaignConfigurationForm, CampaignBulkMessageForm)
from go.base.utils import conversation_or_404


@login_required
def details(request, campaign_key=None):
    """
    TODO: This is a fake implementation, it's not based on anything
    other than displaying the views and perhaps formulating
    some kind of workflow.

    """
    form_general = CampaignGeneralForm()
    form_config = CampaignConfigurationForm()

    if request.method == 'POST':
        form = CampaignGeneralForm(request.POST)
        if form.is_valid():
            conversation_type = form.cleaned_data['type']
            conversation = request.user_api.new_conversation(
                conversation_type, name=form.cleaned_data['name'],
                description=u'', config={})
            messages.info(request, 'Conversation created successfully.')

            action = request.POST.get('action')
            if action == 'draft':
                # save and go back to list.
                return redirect('conversations:index')

            # TODO save and go to next step.
            return redirect('campaigns:message',
                            campaign_key=conversation.key)

    return render(request, 'campaigns/wizard_1_details.html', {
        'form_general': form_general,
        'form_config': form_config,
        'campaign_key': campaign_key
    })


@login_required
def message(request, campaign_key):
    # is this for a conversation or bulk?
    # determine that and redirect.
    conversation = conversation_or_404(request.user_api, campaign_key)
    return redirect('campaigns:message_conversation')


@login_required
def message_conversation(request, campaign_key):
    """Conversations that are difficult:
        1. Talking to your parents about sex.
        2. When your wife complains that you've peed on the toilet seat
            infront of your inlaws.
        3. People who tell you immigration is a problem... When you're an
            immigrant.

        Conversations that are VERY difficult:
        1. This one.
    """
    conversation = conversation_or_404(request.user_api, campaign_key)
    return render(request, 'campaigns/wizard_2_conversation.html', {
        'campaign_key': campaign_key
    })


@login_required
def message_bulk(request, campaign_key):
    """The simpler of the two messages."""
    conversation = conversation_or_404(request.user_api, campaign_key)
    form = CampaignBulkMessageForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        # TODO save and go to next step.
        return redirect('campaigns:contacts', campaign_key=conversation.key)

    return render(request, 'campaigns/wizard_2_message_bulk.html', {
        'form': form,
        'campaign_key': campaign_key
    })


@login_required
def contacts(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        # TODO save and go to next step.
        return redirect('campaigns:preview', campaign_key=conversation.key)

    groups = sorted(request.user_api.list_groups(),
                    key=lambda group: group.created_at,
                    reverse=True)

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

    return render(request, 'campaigns/wizard_3_contacts.html', {
        'paginator': paginator,
        'page': page,
        'pagination_params': pagination_params,
        'campaign_key': campaign_key,
    })


def preview(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'start':
            # 3.2.1.ignition!
            # (Start the conversation)
            return redirect('conversations:index')

    return render(request, 'campaigns/wizard_4_preview.html', {
        'conversation': conversation,
        'campaign_key': campaign_key
    })
