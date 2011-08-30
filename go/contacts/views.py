from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    return redirect(reverse('contacts:groups'))


@login_required
def groups(request):
    groups = request.user.contactgroup_set.all()
    paginator = Paginator(groups, 5)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'groups.html', {
        'paginator': paginator,
        'page': page,
    })


@login_required
def people(request):
    contacts = request.user.contact_set.all()
    return render(request, 'people.html', {
        'contacts': contacts
    })
