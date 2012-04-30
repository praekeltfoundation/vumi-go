from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator

from go.vumitools.conversation import ConversationStore
from go.conversation.forms import ConversationSearchForm


CONVERSATIONS_PER_PAGE = 6


@login_required
def index(request):
    conv_store = ConversationStore.from_django_user(request.user)
    conversations = conv_store.list_conversations()
    search_form = ConversationSearchForm(request.GET)
    search_form.is_valid()

    query = search_form.cleaned_data['query']
    conversation_type = search_form.cleaned_data['conversation_type']
    conversation_status = search_form.cleaned_data['conversation_status']

    if query:
        conversations = [c for c in conversations
                         if query.lower() in c.subject.lower()]

    if conversation_type:
        print conversations
        conversations = [c for c in conversations
                         if c.conversation_type == conversation_type]
        print conversation_type, conversations

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

    # TODO: Decide if we need to put the padding back.

    paginator = Paginator(conversations, CONVERSATIONS_PER_PAGE)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'conversation/index.html', {
        'conversations': conversations,
        'paginator': paginator,
        'page': page,
        'query': query,
        'search_form': search_form,
    })
