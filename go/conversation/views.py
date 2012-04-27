from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from go.conversation.forms import ConversationSearchForm
from go.base.utils import padded_queryset


CONVERSATIONS_PER_PAGE = 6


@login_required
def index(request):
    conversations = request.user.conversation_set.all()
    search_form = ConversationSearchForm(request.GET)
    search_form.is_valid()

    query = search_form.cleaned_data['query']
    conversation_type = search_form.cleaned_data['conversation_type']
    conversation_status = search_form.cleaned_data['conversation_status']

    if query:
        conversations = conversations.filter(subject__icontains=query)

    if conversation_type:
        conversations = conversations.filter(
            conversation_type=conversation_type)

    if conversation_status:
        status_map = {
            'running': lambda c: c.filter(end_time__isnull=True,
                message_batch_set__isnull=False),
            'finished': lambda c: c.filter(end_time__isnull=False),
            'draft': lambda c: c.filter(end_time__isnull=True,
                message_batch_set__isnull=True)
        }

        filter_cb = status_map.get(conversation_status, lambda c: c)
        conversations = filter_cb(conversations)

    if conversations.count() < CONVERSATIONS_PER_PAGE:
        conversations = padded_queryset(conversations, CONVERSATIONS_PER_PAGE)

    paginator = Paginator(conversations, CONVERSATIONS_PER_PAGE)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'conversation/index.html', {
        'conversations': conversations,
        'paginator': paginator,
        'page': page,
        'query': query,
        'search_form': search_form,
    })
