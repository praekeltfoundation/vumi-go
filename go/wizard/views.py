from urllib import urlencode

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages

from go.wizard.forms import (
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
                return redirect('wizard:index')

            # TODO save and go to next step.
            return redirect('wizard:message', campaign_key=conversation.key)

    return render(request, 'wizard_views/wizard_1_details.html', {
        'form_general': form_general,
        'form_config_new': form_config_new,
        'campaign_key': campaign_key
    })


@login_required
def message(request, campaign_key):
    conversation = conversation_or_404(request.user_api, campaign_key)

    to = 'wizard:message_%s' % conversation.conversation_type
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
            return redirect('wizard:index')

        # TODO save and go to next step.
        return redirect('wizard:contacts', campaign_key=conversation.key)

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
            return redirect('wizard:index')

        # TODO save and go to next step.
        return redirect('wizard:contacts', campaign_key=conversation.key)

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
            return redirect('wizard:index')

        group_keys = request.POST.getlist('group')

        # TODO: Remove all groups
        for group_key in group_keys:
            conversation.add_group(group_key)
        conversation.save()

        return redirect('conversations:conversation',
                        campaign_key=conversation.key, path_suffix='')

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
def pricing(request):
    return render(request, 'conversations/pricing.html', {
    })
