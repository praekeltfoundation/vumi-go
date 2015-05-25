from urllib import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages

from go.conversation.forms import (
    NewConversationForm, ConversationSearchForm, ReplyToMessageForm)
from go.base.utils import (
    get_conversation_view_definition, conversation_or_404)


CONVERSATIONS_PER_PAGE = 12


@login_required
def index(request):
    # grab the fields from the GET request
    user_api = request.user_api
    conversation_types = [(app['namespace'], app['display_name'])
                          for app in user_api.applications().values()]
    search_form = ConversationSearchForm(
        request.GET, conversation_types=conversation_types)
    search_form.is_valid()

    conversation_status = search_form.cleaned_data['conversation_status']
    conversation_type = search_form.cleaned_data['conversation_type']
    query = search_form.cleaned_data['query']

    get_conversations = {
        'running': user_api.running_conversations,
        'finished': user_api.archived_conversations,
        'draft': user_api.draft_conversations,
    }.get(conversation_status, user_api.active_conversations)

    conversations = [user_api.wrap_conversation(c)
                        for c in get_conversations()]

    if conversation_type:
        conversations = [c for c in conversations
                         if c.conversation_type == conversation_type]

    if query:
        conversations = [c for c in conversations
                         if query.lower() in c.name.lower()]

    # sort with newest first
    conversations = sorted(conversations, key=lambda c: c.created_at,
                            reverse=True)

    paginator = Paginator(conversations, CONVERSATIONS_PER_PAGE)
    try:
        page = paginator.page(request.GET.get('p', 1))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    pagination_params = urlencode({
        'query': query,
        'conversation_status': conversation_status,
        'conversation_type': conversation_type,
        })

    return render(request, 'conversation/dashboard.html', {
        'conversations': conversations,
        'paginator': paginator,
        'pagination_params': pagination_params,
        'page': page,
        'query': query,
        'search_form': search_form,
    })


@login_required
def conversation(request, conversation_key, path_suffix):
    conv = conversation_or_404(request.user_api, conversation_key)
    view_def = get_conversation_view_definition(
        conv.conversation_type, conv)
    view = view_def.get_view(path_suffix)
    return view(request, conv)


@login_required
def conversation_action(request, conversation_key, action_name):
    conv = conversation_or_404(request.user_api, conversation_key)
    view_def = get_conversation_view_definition(
        conv.conversation_type, conv)
    view = view_def.get_action_view(action_name)
    return view(request, conv)


@login_required
def new_conversation(request):
    if request.method == 'POST':
        form = NewConversationForm(request.user_api, request.POST)
        if form.is_valid():
            conversation_type = form.cleaned_data['conversation_type']

            view_def = get_conversation_view_definition(conversation_type)
            name = form.cleaned_data['name']
            description = form.cleaned_data['description']
            config = view_def._conv_def.get_default_config(name, description)

            conv = request.user_api.new_conversation(
                conversation_type, name=name,
                description=description, config=config,
                extra_endpoints=list(view_def.extra_static_endpoints))
            conv = request.user_api.wrap_conversation(conv)
            conv.start()

            messages.info(request, 'Conversation created successfully.')

            # Get a new view_def with a conversation object in it.
            view_def = get_conversation_view_definition(
                conv.conversation_type, conv)

            next_view = 'show'
            if view_def.is_editable:
                next_view = 'edit'

            return redirect(view_def.get_view_url(
                next_view, conversation_key=conv.key))
    else:
        form = NewConversationForm(request.user_api)
    return render(request, 'conversation/new.html', {
        'conversation_form': form,
    })


# TODO: The following should probably be moved over to view_definition.py

@login_required
def incoming_detail(request, conversation_key, contact_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    form = ReplyToMessageForm()

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

    return render(request, 'conversation/incoming_detail.html', {
        'conversation': conversation,
        'form': form,
        'message_list': message_list
    })
