from urllib import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponse

from go.conversation.forms import ConversationSearchForm
from go.base.utils import get_conversation_view_definition, conversation_or_404
from go.conversation_tmp.forms import CampaignGeneralForm


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
        'finished': user_api.finished_conversations,
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
@require_POST
def new_conversation(request):
    # TODO: description?
    form = CampaignGeneralForm(request.POST)
    if not form.is_valid():
        # TODO: Something more sensible here?
        return HttpResponse(
            "Invalid form: %s" % (form.errors,), status=400)
    conversation_type = form.cleaned_data['type']
    conv = request.user_api.new_conversation(
        conversation_type, name=form.cleaned_data['name'],
        description=u'', config={})
    messages.info(request, 'Conversation created successfully.')

    view_def = get_conversation_view_definition(
        conv.conversation_type, conv)

    # TODO: Better workflow here?

    next_view = 'show'
    action = request.POST.get('action')
    if action == 'draft':
        # save and go back to list.
        return redirect('conversations:index')
    elif view_def.edit_conversation_forms is not None:
        next_view = 'edit'

    return redirect(view_def.get_view_url(
        next_view, conversation_key=conv.key))
