from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from go.conversation.models import Conversation
from go.base.utils import padded_queryset


@login_required
def home(request):
    latest_conversations = padded_queryset(Conversation.objects.all(), size=6)
    return render(request, 'home.html', {
        'latest_conversations': latest_conversations
    })


def todo(request):  # pragma: no cover
    return render(request, 'todo.html', {
    })
