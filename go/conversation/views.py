from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib import messages
from django.conf import settings
from go.conversation.models import (Conversation, ConversationSendError,
                                    get_client_init_delivery_classes)
from go.conversation.forms import (ConversationForm, SelectDeliveryClassForm,
                            BulkSendConversationForm, ConversationGroupForm)
from go.contacts.forms import (NewContactGroupForm, UploadContactsForm,
    SelectContactGroupForm)
from go.contacts.models import Contact, ContactGroup
from go.base.utils import padded_queryset, make_read_only_form
from datetime import datetime


CONVERSATIONS_PER_PAGE = 6

@login_required
def new(request):
    if request.POST:
        form = BulkSendConversationForm(request.POST)
        if form.is_valid():
            conversation = form.save(commit=False)
            conversation.user = request.user
            conversation.save()
            messages.add_message(request, messages.INFO,
                'Conversation Created')
            return redirect(reverse('conversations:people',
                kwargs={'conversation_pk': conversation.pk}))
    else:
        form = BulkSendConversationForm(initial={
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
        })

    return render(request, 'conversation/new.html', {
        'form': form,
        'delivery_classes': get_client_init_delivery_classes(),
    })


@login_required
def upload(request, conversation_pk):
    """
    TODO: This view is still too big.
    """
    conversation = get_object_or_404(Conversation, pk=conversation_pk)
    if request.POST:
        # first parse the CSV file and create Contact instances
        # from them for attaching to a group later
        upload_contacts_form = UploadContactsForm(request.POST,
            request.FILES)
        delivery_class = SelectDeliveryClassForm(request.POST)
        if upload_contacts_form.is_valid() and delivery_class.is_valid():
            contacts = Contact.create_from_csv_file(request.user,
                request.FILES['file'], settings.VUMI_COUNTRY_CODE)
            if request.POST.get('name'):
                new_contact_group_form = NewContactGroupForm(request.POST)
                if new_contact_group_form.is_valid():
                    group = new_contact_group_form.save(commit=False)
                    group.user = request.user
                    group.save()
                    group.add_contacts(contacts)

                    # set the delivery class
                    clean_data = delivery_class.cleaned_data
                    conversation.delivery_class = clean_data['delivery_class']
                    conversation.groups.add(group)
                    conversation.save()
                    messages.add_message(request, messages.INFO,
                        'Contacts uploaded to the group and linked '
                        'to the conversation')
                    return redirect(reverse('conversations:send', kwargs={
                        'conversation_pk': conversation.pk,
                    }))
                else:
                    select_contact_group_form = SelectContactGroupForm()

            if request.POST.get('contact_group'):
                select_contact_group_form = SelectContactGroupForm(
                    request.POST)
                if select_contact_group_form.is_valid():
                    cleaned_data = select_contact_group_form.cleaned_data
                    group = cleaned_data['contact_group']
                    group.add_contacts(contacts)

                    # set the delivery class
                    clean_data = delivery_class.cleaned_data
                    conversation.delivery_class = clean_data['delivery_class']
                    conversation.groups.add(group)
                    conversation.save()
                    messages.add_message(request, messages.INFO,
                        'Contacts uploaded to the group and linked '
                        'to the conversation')
                    return redirect(reverse('conversations:send', kwargs={
                        'conversation_pk': conversation.pk,
                    }))
                else:
                    new_contact_group_form = NewContactGroupForm()
        else:
            new_contact_group_form = NewContactGroupForm()
            select_contact_group_form = SelectContactGroupForm()
            messages.add_message(request, messages.ERROR,
                'Something is wrong with the file you tried to upload.')
    else:
        upload_contacts_form = UploadContactsForm()
        new_contact_group_form = NewContactGroupForm()
        select_contact_group_form = SelectContactGroupForm()

    return render(request, 'conversation/upload.html', {
        'conversation': conversation,
        'upload_contacts_form': upload_contacts_form,
        'new_contact_group_form': new_contact_group_form,
        'select_contact_group_form': select_contact_group_form,
        'country_code': settings.VUMI_COUNTRY_CODE,
        'delivery_class': SelectDeliveryClassForm(),
    })


@login_required
def people(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    groups_for_user = ContactGroup.objects.filter(user=request.user)
    if request.POST:
        group_form = ConversationGroupForm(request.POST)
        group_form.fields['groups'].queryset = groups_for_user
        if group_form.is_valid():
            groups = group_form.cleaned_data['groups']
            # link to the conversation
            for group in groups:
                conversation.groups.add(group)
            conversation.save()
            messages.add_message(request, messages.INFO,
                'The selected groups have been added to the conversation')
            return redirect(reverse('conversations:send', kwargs={
                'conversation_pk': conversation.pk}))

    conversation_form = make_read_only_form(
                            BulkSendConversationForm(instance=conversation))

    group_form = ConversationGroupForm(request.POST)
    group_form.fields['groups'].queryset = groups_for_user

    return render(request, 'conversation/people.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'group_form': group_form,
        'delivery_classes': get_client_init_delivery_classes(),
    })


@login_required
def send(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)

    if request.method == 'POST':
        try:
            conversation.send_messages()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('conversations:send', kwargs={
                'conversation_pk': conversation.pk}))
        messages.add_message(request, messages.INFO, 'Conversation started')
        return redirect(reverse('conversations:show', kwargs={
            'conversation_pk': conversation.pk}))

    conversation_form = make_read_only_form(BulkSendConversationForm(
                                                instance=conversation))
    group_form = make_read_only_form(ConversationGroupForm(initial={
        'groups': conversation.groups.all()
    }))

    return render(request, 'conversation/send.html', {
        'conversation': conversation,
        'conversation_form': conversation_form,
        'group_form': group_form,
    })


@login_required
def start(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.method == 'POST':
        try:
            conversation.send_messages()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return redirect(reverse('conversations:start', kwargs={
                'conversation_pk': conversation.pk}))
        messages.add_message(request, messages.INFO, 'Conversation started')
        return redirect(reverse('conversations:show', kwargs={
            'conversation_pk': conversation.pk}))
    return render(request, 'conversation/start.html', {
        'conversation': conversation,
    })


@login_required
def show(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    return render(request, 'conversation/show.html', {
        'conversation': conversation,
    })


@login_required
def end(request, conversation_pk):
    conversation = get_object_or_404(Conversation, pk=conversation_pk,
        user=request.user)
    if request.method == 'POST':
        conversation.end_conversation()
        messages.add_message(request, messages.INFO, 'Conversation ended')
    return redirect(reverse('conversations:show', kwargs={
        'conversation_pk': conversation.pk}))


@login_required
def index(request):
    conversations = request.user.conversation_set.all()
    query = request.GET.get('q', '')
    if query:
        conversations = conversations.filter(subject__icontains=query)
    if conversations.count() < CONVERSATIONS_PER_PAGE:
        conversations = padded_queryset(conversations, CONVERSATIONS_PER_PAGE)
    paginator = Paginator(conversations, CONVERSATIONS_PER_PAGE)
    page = paginator.page(request.GET.get('p', 1))
    return render(request, 'conversation/index.html', {
        'conversations': conversations,
        'paginator': paginator,
        'page': page,
        'query': query,
    })
