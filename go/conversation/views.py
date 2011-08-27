from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from go.conversation.models import Conversation
from go.conversation import forms
from datetime import datetime

@login_required
def new(request):
    if request.POST:
        form = forms.ConversationForm(request.POST)
        if form.is_valid():
            conversation = form.save(commit=False)
            conversation.owner = request.user
            conversation.save()
            return HttpResponseRedirect(reverse('conversation:participants', 
                kwargs={'conversation_pk': conversation.pk}))
        print form.errors
    else:
        form = forms.ConversationForm(initial={
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M')
        })
    return render(request, 'new.html', {
        'form': form
    })

@login_required
def participants(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk)
    return render(request, 'participants.html', {
        'conversation': conversation
    })