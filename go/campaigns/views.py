from django.shortcuts import render, redirect


from go.campaigns.forms import CampaignGeneralForm, CampaignConfigurationForm


def details(request, key=None):
    """
    NOTE: This is a fake implementation, it's not based on anything
    other than displaything the views and perhaps formulating
    some kind of workflow.

    """
    form_general = CampaignGeneralForm()
    form_config = CampaignConfigurationForm()

    if request.POST:

        action = request.POST.get('action')
        if action == 'draft':
            return redirect('conversations:index')
            # save and go back to list.

        # save and go to next step.
        return redirect('campaigns:message', campaign_key='fakekeydawg')

    return render(request, 'campaigns/wizard_1_details.html', {
        'form_general': form_general,
        'form_config': form_config
    })


def message(request, campaign_key):
    return redirect('campaigns:message_bulk', campaign_key=campaign_key)


def message_bulk(request, campaign_key):
    return render(request, 'campaigns/wizard_2_message_bulk.html')


def message_conversation(request, campaign_key):
    # is this for a conversation or bulk?
    # determine that and redirect.

    return render(request, 'campaigns/wizard_2_conversation.html')
