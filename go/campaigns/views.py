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

    conversation = conversation_or_404(request.user_api, campaign_key)
    form_general = CampaignGeneralForm(data={'name': conversation.name})
    form_config_new = CampaignConfigurationForm()

    if request.method == 'POST':
        form = CampaignGeneralForm(request.POST)
        if form.is_valid():
            conversation_type = form.cleaned_data['kind']
            conversation = request.user_api.new_conversation(
                conversation_type, name=form.cleaned_data['name'],
                description=u'', config={})
            messages.info(request, 'Conversation created successfully.')

            action = request.POST.get('action')
            if action == 'draft':
                # save and go back to list.
                return redirect('conversations:index')

            # TODO save and go to next step.
            return redirect('campaigns:message', campaign_key=conversation.key)


    return render(request, 'campaigns/wizard_1_details.html', {
        'form_general': form_general,
        'form_config_new': form_config_new,
        'campaign_key': campaign_key
    })


@login_required
def message(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)

    to = 'campaigns:message_%s' % conversation.conversation_type
    return redirect(to, campaign_key=conversation.key)


@login_required
def message_survey(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        # TODO save and go to next step.
        return redirect('campaigns:contacts', campaign_key=conversation.key)

    return render(request, 'campaigns/wizard_2_survey.html', {
        'campaign_key': campaign_key,
        'conversation': conversation
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
        'conversation': conversation,
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

        group_keys = request.POST.getlist('group')
        for group_key in group_keys:
            conversation.add_group(group_key)
        conversation.save()

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


@login_required
def preview(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)

    contact_store = request.user_api.contact_store
    groups = dict((group.name, contact_store.count_contacts_for_group(group))
                  for group in conversation.get_groups())

    return render(request, 'campaigns/wizard_4_preview.html', {
        'conversation': conversation,
        'campaign_key': campaign_key,
        'groups': groups,
    })


@login_required
def incoming_list(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)

    # TODO: Where would I get conversation data?
    # FAKE DATA FOR BADLARD.
    message_list = (
        {'contact': '07922 539 521', 'threads': 35, 'date': '2013-03-21'},
        {'contact': '55555 539 521', 'threads': 27, 'date': '2013-03-21'},
        {'contact': '07922 222 521', 'threads': 51, 'date': '2013-03-21'},
        {'contact': '22222 539 222', 'threads': 99, 'date': '2013-03-21'},
    )

    return render(request, 'campaigns/incoming_list.html', {
        'conversation': conversation,
        'message_list': message_list
    })


@login_required
def incoming_detail(request, campaign_key, contact_key):
    conversation = conversation_or_404(request.user_api, campaign_key)
    form = CampaignBulkMessageForm()

    if request.method == 'POST':
        # TODO: process sending message from form
        pass

    # TODO: Where would I get conversation data?
    # FAKE DATA FOR BADLARD.
    message_list = (
        {'contact': 'You', 'message': 'Thank you'},
        {'contact': '55555 539 521', 'message': 'Saturday'},
        {'contact': 'You', 'message': 'What days do you eat?'},
        {'contact': '55555 539 521', 'message': 'Hotdogs'},
        {'contact': 'You', 'message': 'What is your favourite meal?'},
    )

    return render(request, 'campaigns/incoming_detail.html', {
        'conversation': conversation,
        'form': form,
        'message_list': message_list
    })


@login_required
def routing(request, campaign_key):
    # TODO Get initial routing model data so we can bootstrap it to page load

    # TODO give stuff to the template
    return render(request, 'campaigns/routing.html', {
    })
