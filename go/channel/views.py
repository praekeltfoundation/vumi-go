import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, Http404
from django.contrib import messages

from go.channel.forms import NewChannelForm
from go.channel.view_definition import ChannelViewDefinitionBase


logger = logging.getLogger(__name__)


@login_required
def index(request):
    raise NotImplementedError("TODO: List channels")


@login_required
def new_channel(request):
    """
    TODO: Clean this thing up and figure out exactly what we need to do here.
    """

    if request.method == 'POST':
        form = NewChannelForm(request.user_api, request.POST)
        if form.is_valid():
            # TODO: Better validation?
            pool, tag = form.cleaned_data['channel'].split(':')
            if tag:
                got_tag = request.user_api.acquire_specific_tag((pool, tag))
            else:
                got_tag = request.user_api.acquire_tag(pool)

            messages.info(request, 'Acquired tag: %r.' % (got_tag,))

            # TODO save and go to next step.
            return redirect('conversations:index')
        else:
            raise ValueError(repr('Error: %s' % (form.errors,)))

    new_channel_form = NewChannelForm(request.user_api)
    return render(request, 'channel/new.html', {
        'new_channel_form': new_channel_form,
    })


class CheapPlasticChannel(object):
    """Thin wrapper around a tagpool+tag.

    TODO: Replace this with an actual channel object.
    """

    def __init__(self, tagpool, tag, tagpool_metadata):
        self.tagpool = tagpool
        self.tag = tag
        self.tagpool_metadata = tagpool_metadata
        self.key = u'%s:%s' % (tagpool, tag)
        self.name = tag

    def release(self, user_api):
        user_api.release_tag(self.key)


class ChannelDefinition(object):
    """Definition of channel lifecycle and possible actions.

    TODO: Replace this standin with a real thing once we have actual channels.
    """

    channel_type = None
    display_name = 'Channel'

    def __init__(self, channel=None):
        self.channel = channel


class ChannelViewDefinition(ChannelViewDefinitionBase):
    pass


def channel_or_404(user_api, channel_key):
    # TODO: Replace this with a real thing when we have channel models.
    pool, _, tag = channel_key.partition(':')
    tags = user_api.list_endpoints()
    if (pool, tag) not in tags:
        raise Http404

    tagpool_meta = user_api.api.tpm.get_metadata(pool)
    return CheapPlasticChannel(pool, tag, tagpool_meta)


def get_channel_view_definition(channel):
    # TODO: Replace this with a real thing when we have channel models.
    chan_def = ChannelDefinition(channel)
    return ChannelViewDefinition(chan_def)


@login_required
def channel(request, channel_key, path_suffix):
    # TODO: Rewrite this when we have a proper channel object.
    # NOTE: We assume "channel_key" is "tagpool:tag" for now.
    channel = channel_or_404(request.user_api, channel_key)
    view_def = get_channel_view_definition(channel)
    view = view_def.get_view(path_suffix)
    return view(request, channel)
