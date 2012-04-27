from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from go.base.utils import padded_queryset


@login_required
def home(request):
    conversations = request.user.conversation_set.all()
    latest_conversations = padded_queryset(conversations, size=6)
    return render(request, 'base/home.html', {
        'latest_conversations': latest_conversations
    })


def todo(request):  # pragma: no cover
    return render(request, 'base/todo.html', {
    })
