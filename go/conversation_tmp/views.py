from urllib import urlencode
import json

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.conf import settings
import requests

from go.conversation_tmp.forms import (
    CampaignGeneralForm, CampaignConfigurationForm, CampaignBulkMessageForm,
    CampaignSurveryInitiateForm)
from go.base.utils import conversation_or_404


@login_required
def details(request, campaign_key=None):
    """
    TODO: This is a fake implementation, it's not based on anything
    other than displaying the views and perhaps formulating
    some kind of workflow.

    """

    form_general = CampaignGeneralForm()
    form_config_new = CampaignConfigurationForm()

    if campaign_key:
        conversation = conversation_or_404(request.user_api, campaign_key)
        form_general = CampaignGeneralForm(data={'name': conversation.name})

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
                return redirect('conversations_tmp:index')

            # TODO save and go to next step.
            return redirect('conversations_tmp:message', campaign_key=conversation.key)

    return render(request, 'wizard_views/wizard_1_details.html', {
        'form_general': form_general,
        'form_config_new': form_config_new,
        'campaign_key': campaign_key
    })


@login_required
def message(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)

    to = 'conversations_tmp:message_%s' % conversation.conversation_type
    return redirect(to, campaign_key=conversation.key)


@login_required
def message_survey(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)
    initiate_form = CampaignSurveryInitiateForm()
    if request.method == 'POST':
        initiate_form = CampaignSurveryInitiateForm(request.POST)
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations_tmp:index')

        # TODO save and go to next step.
        return redirect('conversations_tmp:contacts', campaign_key=conversation.key)

    return render(request, 'wizard_views/wizard_2_survey.html', {
        'campaign_key': campaign_key,
        'conversation': conversation,
        'initiate_form': initiate_form
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
            return redirect('conversations_tmp:index')

        # TODO save and go to next step.
        return redirect('conversations_tmp:contacts', campaign_key=conversation.key)

    return render(request, 'wizard_views/wizard_2_message_bulk.html', {
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
            return redirect('conversations_tmp:index')

        group_keys = request.POST.getlist('group')

        # TODO: Remove all groups
        for group_key in group_keys:
            conversation.add_group(group_key)
        conversation.save()

        return redirect('/conversations/%s/' % conversation.key)

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
        'campaign_key': campaign_key,
    })

@login_required
def incoming_list(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)

    # TODO: Conversation data.
    # FAKE DATA FOR BADLARD.
    message_list = (
        {'contact': '07922 539 521', 'threads': 35, 'date': '2013-03-21'},
        {'contact': '55555 539 521', 'threads': 27, 'date': '2013-03-21'},
        {'contact': '07922 222 521', 'threads': 51, 'date': '2013-03-21'},
        {'contact': '22222 539 222', 'threads': 99, 'date': '2013-03-21'},
    )

    return render(request, 'conversations/incoming_list.html', {
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

    # TODO: Conversation data.
    # FAKE DATA FOR BADLARD.
    message_list = (
        {'contact': 'You', 'message': 'Thank you'},
        {'contact': '55555 539 521', 'message': 'Saturday'},
        {'contact': 'You', 'message': 'What days do you eat?'},
        {'contact': '55555 539 521', 'message': 'Hotdogs'},
        {'contact': 'You', 'message': 'What is your favourite meal?'},
    )

    return render(request, 'conversations/incoming_detail.html', {
        'conversation': conversation,
        'form': form,
        'message_list': message_list
    })


@login_required
def pricing(request):
    return render(request, 'conversations/pricing.html', {
    })


@login_required
def routing(request):
    # TODO: Better Go API client.

    url = settings.GO_API_URL
    auth = ('session_id', request.COOKIES['sessionid'])
    req_data = {
        "params": [request.user_api.user_account_key],
        "jsonrpc": "2.0",
        "method": "routing_table",
        "id": None,
    }
    data = json.dumps(req_data)

    r = requests.post(url, auth=auth, data=data)

    model_data = {
        'campaign_id': request.user_api.user_account_key,
    }
    model_data.update(r.json['result'])

    return render(request, 'conversations/routing.html', {
        'model_data': json.dumps(model_data),
    })
