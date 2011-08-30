from django.shortcuts import render, redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from go.contacts import forms
from go.contacts.models import ContactGroup


@login_required
def index(request):
    return redirect(reverse('contacts:groups'))


@login_required
def groups(request):
    if request.POST:
        new_contact_group_form = forms.NewContactGroupForm(request.POST)
        if new_contact_group_form.is_valid():
            group = new_contact_group_form.save(commit=False)
            group.user = request.user
            group.save()
            return redirect(reverse('contacts:group', kwargs={
                'group_pk': group.pk}))
    else:
        new_contact_group_form = forms.NewContactGroupForm()
    
    groups = request.user.contactgroup_set.all()
    paginator = Paginator(groups, 5)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'groups.html', {
        'paginator': paginator,
        'page': page,
        'new_contact_group_form': new_contact_group_form,
    })

@login_required
def group(request, group_pk):
    group = get_object_or_404(ContactGroup, pk=group_pk, user=request.user)
    return render(request, 'group.html', {
        'group': group,
    })

@login_required
def people(request):
    contacts = request.user.contact_set.all()
    return render(request, 'people.html', {
        'contacts': contacts
    })
