from django.shortcuts import render


def todo(request):  # pragma: no cover
    return render(request, 'base/todo.html', {
    })
