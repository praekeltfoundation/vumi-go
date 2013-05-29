from urllib import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from go.conversation.forms import ConversationSearchForm
from go.base.utils import get_conversation_definition, conversation_or_404
from go.conversation.conversation_views import ConversationViewFinder


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

    # We want to pad with None to a multiple of the conversation size.
    last_page_size = len(conversations) % CONVERSATIONS_PER_PAGE
    padding = [None] * (CONVERSATIONS_PER_PAGE - last_page_size)
    conversations += padding

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

    return render(request, 'conversation/index.html', {
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
    conv_def = get_conversation_definition(conv.conversation_type)
    finder = ConversationViewFinder(conv_def(conv))
    view = finder.get_view(path_suffix)
    return view(request, conv)


@login_required
def new_conversation(request, conversation_type):
    conv_def = get_conversation_definition(conversation_type)
    finder = ConversationViewFinder(conv_def(None))
    view = finder.get_new_conversation_view()
    return view(request, conversation_type)
