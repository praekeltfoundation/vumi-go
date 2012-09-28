from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.contrib import messages

from go.conversation.forms import ConversationSearchForm


CONVERSATIONS_PER_PAGE = 6


@login_required
def index(request):
    conv_store = request.user_api.conversation_store
    conversations = [request.user_api.wrap_conversation(conversation)
                     for conversation in conv_store.list_conversations()]
    conversations = sorted(conversations, key=lambda c: c.created_at,
                            reverse=True)
    search_form = ConversationSearchForm(request.GET)
    search_form.is_valid()

    query = search_form.cleaned_data['query']
    conversation_type = search_form.cleaned_data['conversation_type']
    conversation_status = search_form.cleaned_data['conversation_status']

    if query:
        conversations = [c for c in conversations
                         if query.lower() in c.subject.lower()]

    if conversation_type:
        conversations = [c for c in conversations
                         if c.conversation_type == conversation_type]

    if conversation_status:
        if conversation_status == 'running':
            conversations = [c for c in conversations
                             if c.end_timestamp is None
                             and len(c.batches.keys()) > 0]
        elif conversation_status == 'finished':
            conversations = [c for c in conversations
                             if c.end_timestamp is not None]
        elif conversation_status == 'draft':
            conversations = [c for c in conversations
                             if c.end_timestamp is None
                             and len(c.batches.keys()) == 0]
        else:
            raise ValueError(
                "Unknown conversation status: %s" % (conversation_status,))

    if not (conversation_type or conversation_status or query):
        active_conversations = request.user_api.active_conversations()
        conversations = [request.user_api.wrap_conversation(conversation) for
                    conversation in active_conversations]

        has_active_sms_conversation = any([c.delivery_class == 'sms'
                                           for c in active_conversations])
        has_archived_conversations = conv_store.list_conversations()
        if not (has_active_sms_conversation) and has_archived_conversations:
            messages.error(request, "You do not have any active SMS "
                "conversations. Opt-outs will not work until you do.")

    # We want to pad with None to a multiple of the conversation size.
    # NOTE: If we have no conversations, we don't pad.
    last_page_size = len(conversations) % CONVERSATIONS_PER_PAGE
    padding = [None] * (CONVERSATIONS_PER_PAGE - last_page_size)
    conversations += padding

    paginator = Paginator(conversations, CONVERSATIONS_PER_PAGE)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'conversation/index.html', {
        'conversations': conversations,
        'paginator': paginator,
        'page': page,
        'query': query,
        'search_form': search_form,
    })
