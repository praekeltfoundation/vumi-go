from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from go.conversation.models import Conversation

NUM_CONVERSATIONS_TO_DISPLAY = 6

@login_required
def home(request):
    latest_conversations = Conversation.objects.all()[:NUM_CONVERSATIONS_TO_DISPLAY]
    if latest_conversations.count() < NUM_CONVERSATIONS_TO_DISPLAY:
        difference = NUM_CONVERSATIONS_TO_DISPLAY - latest_conversations.count()
        filler = [None] * difference
        latest_conversations = list(latest_conversations)
        latest_conversations.extend(filler)
        print latest_conversations
    return render(request, 'home.html', {
        'latest_conversations': latest_conversations
    })


def todo(request):  # pragma: no cover
    return render(request, 'todo.html', {
    })
