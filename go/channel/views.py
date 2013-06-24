from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from go.channel.forms import CampaignConfigurationForm


@login_required
def index(request):
    raise NotImplementedError("TODO: List channels")


@login_required
def new_channel(request):
    """
    TODO: Clean this thing up and figure out exactly what we need to do here.
    """

    if request.method == 'POST':
        form = CampaignConfigurationForm(request.user_api, request.POST)
        if form.is_valid():
            # TODO: Acquire tag, etc.
            messages.info(request, 'Pretended to create channel: %r - %r.' % (
                form.cleaned_data['countries'], form.cleaned_data['channels']))

            # TODO save and go to next step.
            return redirect('conversations:index')
        else:
            raise ValueError(repr('Error: %s' % (form.errors,)))

    form_config_new = CampaignConfigurationForm(request.user_api)
    return render(request, 'channel/new.html', {
        'form_config_new': form_config_new,
    })
