from django.http import Http404
from django.shortcuts import render, redirect

from .forms import CampaignForm


def new(request):
    """
    I guess we would actually use a form here.

    But I don't know how this hooks up with the models;
    So... I'm going to maybe fake it?

    Ok. I won't.

    I'll create a form, but you guys will have to hook it up properly.
    """

    form = CampaignForm()

    

    return  render(request, 'campaigns/wizard_details.html', {
        'form': form
    })
