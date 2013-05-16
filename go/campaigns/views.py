from django.http import HttpResponse
from django.shortcuts import render, redirect

from go.campaigns.forms import (
    CampaignGeneralForm, CampaignConfigurationForm, CampaignBulkMessageForm)


def details(request, campaign_key=None):
    """
    TODO: This is a fake implementation, it's not based on anything
    other than displaying the views and perhaps formulating
    some kind of workflow.

    """
    form_general = CampaignGeneralForm()
    form_config = CampaignConfigurationForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        # TODO save and go to next step.
        return redirect('campaigns:message', campaign_key='fakekeydawg')

    return render(request, 'campaigns/wizard_1_details.html', {
        'form_general': form_general,
        'form_config': form_config,
        'campaign_key': campaign_key
    })


def message(request, campaign_key):
    # is this for a conversation or bulk?
    # determine that and redirect.
    return redirect('campaigns:message_bulk', campaign_key=campaign_key)


def message_bulk(request, campaign_key):
    """The simpler of the two messages."""
    form = CampaignBulkMessageForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        # TODO save and go to next step.
        return redirect('campaigns:contacts', campaign_key=campaign_key)

    return render(request, 'campaigns/wizard_2_message_bulk.html', {
        'form': form,
        'campaign_key': campaign_key
    })


def message_conversation(request, campaign_key):
    return render(request, 'campaigns/wizard_2_conversation.html')


def contacts(request, campaign_key):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('campaigns:index')

        return redirect('campaigns:preview', campaign_key=campaign_key)

    return render(request, 'campaigns/wizard_3_contacts.html', {
        'campaign_key': campaign_key
    })


def preview(request, campaign_key):
    return render(request, 'campaigns/wizard_4_preview.html', {
        'campaign_key': campaign_key
    })
