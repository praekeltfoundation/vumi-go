from django.shortcuts import render, redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from go.contacts import forms
from go.contacts.models import ContactGroup, Contact


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
            messages.add_message(request, messages.INFO, 'New group created')
            return redirect(reverse('contacts:group', kwargs={
                'group_pk': group.pk}))
    else:
        new_contact_group_form = forms.NewContactGroupForm()

    groups = request.user.contactgroup_set.all()
    paginator = Paginator(groups, 5)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'contacts/groups.html', {
        'paginator': paginator,
        'page': page,
        'new_contact_group_form': new_contact_group_form,
    })


@login_required
def group(request, group_pk):
    group = get_object_or_404(ContactGroup, pk=group_pk, user=request.user)
    query = request.GET.get('q', None)
    if query:
        selected_contacts = group.contact_set.filter(
            Q(surname__icontains=query) | Q(name__icontains=query))
        selected_letter = None
    else:
        selected_letter = request.GET.get('l', 'a').lower()
        selected_contacts = group.contact_set.filter(
            surname__istartswith=selected_letter)
    return render(request, 'contacts/group.html', {
        'group': group,
        'selected_letter': selected_letter,
        'selected_contacts': selected_contacts,
        'query': query,
    })


@login_required
def people(request):
    if request.POST:
        # first parse the CSV file and create Contact instances
        # from them for attaching to a group later
        upload_contacts_form = forms.UploadContactsForm(request.POST,
            request.FILES)
        if upload_contacts_form.is_valid():
            contacts = Contact.create_from_csv_file(request.user,
                request.FILES['file'])
            if request.POST.get('name'):
                new_contact_group_form = forms.NewContactGroupForm(request.POST)
                if new_contact_group_form.is_valid():
                    group = new_contact_group_form.save(commit=False)
                    group.user = request.user
                    group.save()
                    group.add_contacts(contacts)
                    return redirect(reverse('contacts:group', kwargs={
                        'group_pk': group.pk
                    }))
    
            if request.POST.get('contact_group'):
                select_contact_group_form = forms.SelectContactGroupForm(
                    request.POST)
                if select_contact_group_form.is_valid():
                    cleaned_data = select_contact_group_form.cleaned_data
                    group = cleaned_data['contact_group']
                    group.add_contacts(contacts)
                    return redirect(reverse('contacts:group', kwargs={
                        'group_pk': group.pk
                    }))
        else:
            messages.add_message(request, messages.ERROR,
                'Something went wrong with the upload.')


    query = request.GET.get('q', None)
    contacts = request.user.contact_set.all()
    if query:
        selected_contacts = contacts.filter(
            Q(surname__icontains=query) | Q(name__icontains=query))
        selected_letter = None
    else:
        selected_letter = request.GET.get('l', 'a').lower()
        selected_contacts = contacts.filter(
            surname__istartswith=selected_letter)
        
    return render(request, 'contacts/people.html', {
        'contacts': contacts,
        'selected_contacts': selected_contacts,
        'selected_letter': selected_letter,
        'query': query,
    })


@login_required
def person(request, person_pk):
    contact = get_object_or_404(Contact, pk=person_pk, user=request.user)
    if request.POST:
        form = forms.ContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.add_message(request, messages.INFO, 'Profile Updated')
            return redirect(reverse('contacts:person', kwargs={
                'person_pk': contact.pk}))
        else:
            messages.add_message(request, messages.ERROR,
                'Please correct the problem below.')
    else:
        form = forms.ContactForm(instance=contact)
    return render(request, 'contacts/person.html', {
        'contact': contact,
        'form': form,
    })


@login_required
def new_person(request):
    if request.POST:
        form = forms.ContactForm(request.POST,
            instance=Contact(user=request.user))
        if form.is_valid():
            contact = form.save()
            messages.add_message(request, messages.INFO, 'Profile Created')
            return redirect(reverse('contacts:person', kwargs={
                'person_pk': contact.pk}))
        else:
            messages.add_message(request, messages.ERROR,
                'Please correct the problem below.')
    else:
        form = forms.ContactForm()
    return render(request, 'contacts/new_person.html', {
        'form': form,
    })
