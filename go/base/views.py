from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from go.conversation.models import Conversation


@login_required
def home(request):
    latest_conversations = Conversation.objects.recent(limit=6)
    return render(request, 'home.html', {
        'latest_conversations': latest_conversations
    })


def todo(request):  # pragma: no cover
    return render(request, 'todo.html', {
    })
