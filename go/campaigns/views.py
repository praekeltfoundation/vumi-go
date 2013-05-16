from urllib import urlencode

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

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
        'form_config': form_config
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
        return redirect('campaigns:contacts', campaign_key='fakekeydawg')

    return render(request, 'campaigns/wizard_2_message_bulk.html', {
        'form': form
    })


@login_required
def contacts(request, campaign_key):
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
    })


def message_conversation(request, campaign_key):
    return render(request, 'campaigns/wizard_2_conversation.html')


def todo(request, campaign_key):
    return HttpResponse('TODO')
