from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def home(request):
    return render(request, 'home.html', {
    })
    
def todo(request): # pragma: no cover
    return render(request, 'todo.html', {
    })
