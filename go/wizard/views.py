import json
from urllib import urlencode

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages

from go.wizard.forms import Wizard1CreateForm, CampaignBulkMessageForm
from go.conversation.forms import NewConversationForm
from go.channel.forms import NewChannelForm
from go.base.utils import get_conversation_view_definition, conversation_or_404
from go.vumitools.account import RoutingTableHelper


import logging
logger = logging.getLogger(__name__)


@login_required
def create(request, conversation_key=None):
    """
    TODO: This is a fake implementation, it's not based on anything
    other than displaying the views and perhaps formulating
    some kind of workflow.

    """
    wizard_form = Wizard1CreateForm()
    conversation_form = NewConversationForm()
    channel_form = NewChannelForm(request.user_api)

    conversation = None
    if conversation_key:
        conversation = conversation_or_404(request.user_api, conversation_key)
        conversation_form = NewConversationForm(
            data={'name': conversation.name})

    if request.method == 'POST':
        # TODO: Reuse new conversation/channel view logic here.
        posted_conv_form = NewConversationForm(request.POST)
        posted_chan_form = NewChannelForm(request.user_api, request.POST)
        if posted_conv_form.is_valid() and posted_chan_form.is_valid():

            # Create channel
            chan_data = posted_chan_form.cleaned_data
            pool, tag = chan_data['channel'].split(':')
            if tag:
                got_tag = request.user_api.acquire_specific_tag((pool, tag))
            else:
                got_tag = request.user_api.acquire_tag(pool)

            # Create conversation
            conv_data = posted_conv_form.cleaned_data
            conversation_type = conv_data['conversation_type']

            view_def = get_conversation_view_definition(conversation_type)
            conversation = request.user_api.new_conversation(
                conversation_type, name=conv_data['name'],
                description=conv_data['description'], config={},
                extra_endpoints=list(view_def.extra_static_endpoints),
            )
            messages.info(request, 'Conversation created successfully.')

            # TODO: Factor this out into a helper of some kind.
            user_account = request.user_api.get_user_account()
            routing_table = request.user_api.get_routing_table(user_account)
            rt_helper = RoutingTableHelper(routing_table)
            rt_helper.add_oldstyle_conversation(conversation, got_tag)
            user_account.save()

            # TODO save and go to next step.
            return redirect(
                'conversations:conversation',
                conversation_key=conversation.key, path_suffix='')
        else:
            logger.info("Validation failed: %r %r" % (
                posted_conv_form.errors, posted_chan_form.errors))

    return render(request, 'wizard_views/wizard_1_create.html', {
        'wizard_form': wizard_form,
        'conversation_form': conversation_form,
        'channel_form': channel_form,
        'conversation': conversation,
    })


@login_required
def edit(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)

    to = 'wizard:edit_%s' % conversation.conversation_type
    return redirect(to, conversation_key=conversation.key)


@login_required
def edit_survey(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)

    # TODO get existing model data from api and bootstrap it to page load
    model_data = json.dumps({'conversation_key': conversation_key})

    return render(request, 'wizard_views/wizard_2_edit_survey.html', {
        'conversation_key': conversation_key,
        'conversation': conversation,
        'model_data': model_data
    })


@login_required
def edit_bulk_message(request, conversation_key):
    """The simpler of the two messages."""
    conversation = conversation_or_404(request.user_api, conversation_key)
    form = CampaignBulkMessageForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        # TODO save and go to next step.
        return redirect('wizard:contacts', conversation_key=conversation.key)

    return render(request, 'wizard_views/wizard_2_edit_bulk_message.html', {
        'form': form,
        'conversation': conversation,
        'conversation_key': conversation_key
    })


@login_required
def contacts(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        group_keys = request.POST.getlist('group')

        # TODO: Remove all groups
        for group_key in group_keys:
            conversation.add_group(group_key)
        conversation.save()

        return redirect('conversations:conversation',
                        conversation_key=conversation.key, path_suffix='')

    groups = sorted(request.user_api.list_groups(),
                    key=lambda group: group.created_at,
                    reverse=True)

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
        'conversation_key': conversation_key,
        'conversation': conversation,
    })


# TODO: Something sensible with the pricing view.
@login_required
def pricing(request):
    return render(request, 'conversations/pricing.html', {
    })
