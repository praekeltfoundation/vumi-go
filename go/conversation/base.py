import csv
import urllib
from datetime import datetime
from StringIO import StringIO

from django.views.generic import TemplateView
from django.core.paginator import PageNotAnInteger, EmptyPage
from django import forms

from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, Http404
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.conf.urls.defaults import url, patterns
from django.conf import settings
from django.http import HttpResponse

from go.vumitools.conversation.models import (
    CONVERSATION_DRAFT, CONVERSATION_RUNNING, CONVERSATION_FINISHED)
from go.vumitools.exceptions import ConversationSendError
from go.base.django_token_manager import DjangoTokenManager
from go.conversation.forms import (ConversationForm, ConversationGroupForm,
                                    ConfirmConversationForm,
                                    ReplyToMessageForm)
from go.conversation.tasks import (export_conversation_messages,
                                    send_one_off_reply)
from go.base import message_store_client as ms_client
from go.base.utils import (make_read_only_form, conversation_or_404,
                            page_range_window)


class ConversationView(TemplateView):
    template_name = None
    template_base = 'generic'

    # These are set in the constructor, but the attributes must exist already.
    conversation_form = None
    conversation_group_form = None
    conversation_type = None
    conversation_initiator = None
    conversation_display_name = None
    tagpool_filter = None
    edit_conversation_forms = None
    conversation_start_params = None

    def request_setup(self, request, conversation_key):
        """Perform common request setup.

        By default, expects a conversation key and fetches the appropriate
        conversation.
        """
        conversation = conversation_or_404(request.user_api, conversation_key)
        return (conversation,), {}

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        args, kwargs = self.request_setup(request, *args, **kwargs)
        return super(ConversationView, self).dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.get_template_name(self.template_name)]

    def get_template_name(self, name):
        return '%s/%s.html' % (self.template_base, name)

    def redirect_to(self, name, **kwargs):
        return redirect(self.get_view_url(name, **kwargs))

    def get_view_url(self, name, **kwargs):
        return reverse('%s:%s' % (self.conversation_type, name), kwargs=kwargs)

    def make_conversation_form(self, *args, **kw):
        kw.setdefault('tagpool_filter', self.tagpool_filter)
        return self.conversation_form(*args, **kw)

    def get_next_view(self, conversation):
        if conversation.get_status() != CONVERSATION_DRAFT:
            return 'show'
        if self.conversation_initiator == 'client':
            return 'start'
        return 'people'


class NewConversationView(ConversationView):
    template_name = 'new'

    def request_setup(self, request):
        return (), {}

    def get(self, request):
        # We used to put the time in the form, but that's a silly thing to do.
        # Especially since we now ignore it anyway.
        form = self.make_conversation_form(request.user_api, initial={})
        return self.render_to_response({'form': form})

    def post(self, request):
        form = self.make_conversation_form(request.user_api, request.POST)
        if not form.is_valid():
            return self.render_to_response({'form': form})

        copy_keys = [
            'subject',
            'message',
            'delivery_class',
            'delivery_tag_pool',
            ]
        conversation_data = dict((k, form.cleaned_data[k]) for k in copy_keys)

        tag_info = form.cleaned_data['delivery_tag_pool'].partition(':')
        conversation_data['delivery_tag_pool'] = tag_info[0]
        if tag_info[2]:
            conversation_data['delivery_tag'] = tag_info[2]

        # Ignoring start time, because we don't actually do anything with it.
        conversation_data['start_timestamp'] = datetime.utcnow()

        conversation = request.user_api.new_conversation(
            self.conversation_type, **conversation_data)
        messages.add_message(request, messages.INFO,
                             '%s Created' % (self.conversation_display_name,))

        next_view = self.get_next_view(conversation)
        if self.edit_conversation_forms is not None:
            next_view = 'edit'
        return self.redirect_to(next_view, conversation_key=conversation.key)


class PeopleConversationView(ConversationView):
    template_name = 'people'

    def request_setup(self, request, conversation_key):
        conversation = conversation_or_404(request.user_api, conversation_key)
        groups = request.user_api.list_groups()
        return (conversation, groups), {}

    def get(self, request, conversation, groups):
        conversation_form = make_read_only_form(self.make_conversation_form(
                request.user_api, instance=conversation, initial={}))
        return self.render_to_response({
                'conversation': conversation,
                'conversation_form': conversation_form,
                'groups': groups,
                })

    def post(self, request, conversation, groups):
        group_form = self.conversation_group_form(request.POST, groups=groups)
        if not group_form.is_valid():
            return self.get(request, conversation, groups)

        for group in group_form.cleaned_data['groups']:
            conversation.groups.add_key(group)
        conversation.save()
        messages.add_message(request, messages.INFO,
            'The selected groups have been added to the conversation')
        return self.redirect_to('start', conversation_key=conversation.key)


class StartConversationView(ConversationView):
    template_name = 'start'

    def get(self, request, conversation):
        profile = request.user.get_profile()
        account = profile.get_user_account()

        conversation_form = make_read_only_form(self.make_conversation_form(
                request.user_api, instance=conversation, initial={}))
        groups = request.user_api.list_groups()
        group_form = make_read_only_form(
            self.conversation_group_form(groups=groups))

        if self.conversation_initiator == 'client':
            return self.render_to_response({
                    'user_profile': profile,
                    'send_messages': False,
                    'confirm_start_conversation':
                        account.confirm_start_conversation,
                    'conversation': conversation,
                    })
        else:
            conv_groups = []
            for bunch in conversation.groups.load_all_bunches():
                conv_groups.extend(bunch)

            return self.render_to_response({
                    'user_profile': profile,
                    'send_messages': True,
                    'confirm_start_conversation':
                        account.confirm_start_conversation,
                    'conversation': conversation,
                    'conversation_form': conversation_form,
                    'group_form': group_form,
                    'groups': conv_groups,
                    })

    def _start_conversation(self, request, conversation):
        params = {}
        params.update(self.conversation_start_params or {})

        if self.conversation_initiator != 'client':
            params['dedupe'] = request.POST.get('dedupe') == '1'
        try:
            conversation.start(**params)
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return self.redirect_to('start', conversation_key=conversation.key)
        messages.add_message(request, messages.INFO,
                             '%s started' % (self.conversation_display_name,))
        return self.redirect_to('show', conversation_key=conversation.key)

    def _start_via_confirmation(self, request, account, conversation):

        params = {}
        params.update(self.conversation_start_params or {})

        if self.conversation_initiator != 'client':
            params['dedupe'] = request.POST.get('dedupe') == '1'

        # The URL the user will be redirected to post-confirmation
        redirect_to = self.get_view_url('confirm',
                            conversation_key=conversation.key)
        # The token to be sent.
        token_manager = DjangoTokenManager(request.user_api.api.token_manager)
        token = token_manager.generate(redirect_to, user_id=request.user.id,
                                        extra_params=params)
        conversation.send_token_url(token_manager.url_for_token(token),
                                        account.msisdn)
        messages.info(request, 'Confirmation request sent.')
        return self.redirect_to('show', conversation_key=conversation.key)

    def post(self, request, conversation):
        profile = request.user.get_profile()
        account = profile.get_user_account()
        if account.confirm_start_conversation:
            return self._start_via_confirmation(request, account, conversation)
        else:
            return self._start_conversation(request, conversation)


class ConfirmConversationView(ConversationView):
    template_name = 'confirm'

    def get(self, request, conversation):
        # TODO: Ideally we should display a nice message to the user
        #       if they access the page for a conversation that has
        #       already been started.  Currently we just display a 404
        #       page if the token no longer exists because it has
        #       already been used.

        token_manager = DjangoTokenManager(request.user_api.api.token_manager)
        token = request.GET.get('token')
        token_data = token_manager.verify_get(token)
        if not token_data:
            raise Http404
        return self.render_to_response({
            'form': ConfirmConversationForm(initial={'token': token}),
            'conversation': conversation,
            'success': False,
        })

    def post(self, request, conversation):
        token = request.POST.get('token')
        token_manager = DjangoTokenManager(request.user_api.api.token_manager)
        token_data = token_manager.verify_get(token)
        if not token_data:
            raise Http404

        params = token_data.get('extra_params', {})
        user_token, sys_token = token_manager.parse_full_token(token)
        confirmation_form = ConfirmConversationForm(request.POST)
        success = False
        if confirmation_form.is_valid():
            try:
                batch_id = conversation.get_latest_batch_key()
                conversation.start(batch_id=batch_id, **params)
                token_manager.delete(user_token)
                messages.info(request, '%s started succesfully!' %
                              (self.conversation_display_name,))
                success = True
            except ConversationSendError as error:
                messages.error(request, str(error))
        else:
            messages.error('Invalid confirmation form.')

        return self.render_to_response({
            'form': confirmation_form,
            'conversation': conversation,
            'success': success,
        })


class ShowConversationView(ConversationView):
    template_name = 'show'

    def get(self, request, conversation):
        params = {
            'conversation': conversation,
            'is_editable': (self.edit_conversation_forms is not None),
            'user_api': request.user_api,
            }
        status = conversation.get_status()
        templ = lambda name: self.get_template_name('includes/%s' % (name,))

        if status == CONVERSATION_FINISHED:
            params['button_template'] = templ('ended-button')
        elif status == CONVERSATION_RUNNING:
            params['button_template'] = templ('end-button')
        elif status == CONVERSATION_DRAFT:
            params['button_template'] = templ('next-button')
            params['next_url'] = self.get_view_url(
                self.get_next_view(conversation),
                conversation_key=conversation.key)
        return self.render_to_response(params)

    def post(self, request, conversation):
        if '_export_conversation_messages' in request.POST:
            export_conversation_messages.delay(
                request.user_api.user_account_key, conversation.key)
            messages.info(request, 'Conversation messages CSV file export '
                                    'scheduled. CSV file should arrive in '
                                    'your mailbox shortly.')
        if '_send_one_off_reply' in request.POST:
            form = ReplyToMessageForm(request.POST)
            if form.is_valid():
                in_reply_to = form.cleaned_data['in_reply_to']
                content = form.cleaned_data['content']
                send_one_off_reply.delay(
                    request.user_api.user_account_key, conversation.key,
                    in_reply_to, content)
                messages.info(request, 'Reply scheduled for sending.')
            else:
                messages.error(request,
                    'Something went wrong. Please try again.')
                print form.errors
        return self.redirect_to('show', conversation_key=conversation.key)


class AggregatesConversationView(ConversationView):

    def get(self, request, conversation):
        sio = StringIO()
        writer = csv.writer(sio)
        direction = request.GET.get('direction', 'inbound')
        writer.writerows(conversation.get_aggregate_count(direction))
        return HttpResponse(sio.getvalue(),
            content_type='text/csv; charset=utf-8')


class EditConversationView(ConversationView):
    """View for editing conversation data.

    Subclass this and set :attr:`edit_conversation_forms` to a list of tuples
    of the form `('key', FormClass)`.

    The `key` should be a key into the conversation's metadata field. If `key`
    is `None`, the whole of the metadata field will be used.

    If the default behaviour is insufficient or problematic, implement
    :meth:`make_forms` and :meth:`process_forms`. These are the only two
    methods that look at :attr:`edit_conversation_forms`.
    """
    template_name = 'edit'
    edit_conversation_forms = ()

    def _render_forms(self, request, conversation, edit_forms):
        def sum_media(form_list):
            return sum((f.media for f in form_list), forms.Media())

        return self.render_to_response({
                'conversation': conversation,
                'edit_forms_media': sum_media(edit_forms),
                'edit_forms': edit_forms,
                })

    def get(self, request, conversation):
        edit_forms = self.make_forms(conversation)
        return self._render_forms(request, conversation, edit_forms)

    def post(self, request, conversation):
        response = self.process_forms(request, conversation)
        if response is not None:
            return response

        return self.redirect_to(self.get_next_view(conversation),
                                conversation_key=conversation.key)

    def make_form(self, key, form, metadata):
        data = metadata.get(key, {})
        if hasattr(form, 'initial_from_metadata'):
            data = form.initial_from_metadata(data)
        return form(prefix=key, initial=data)

    def make_forms(self, conversation):
        metadata = conversation.get_metadata(default={})
        return [self.make_form(key, edit_form, metadata)
                for key, edit_form in self.edit_conversation_forms]

    def process_form(self, form):
        if hasattr(form, 'to_metadata'):
            return form.to_metadata()
        return form.cleaned_data

    def process_forms(self, request, conversation):
        metadata = conversation.get_metadata(default={})
        edit_forms_with_keys = [
            (key, edit_form_cls(request.POST, prefix=key))
            for key, edit_form_cls in self.edit_conversation_forms]
        edit_forms = [edit_form for _key, edit_form in edit_forms_with_keys]

        for key, edit_form in edit_forms_with_keys:
            # Is this a good idea?
            if not edit_form.is_valid():
                return self._render_forms(request, conversation, edit_forms)
            metadata[key] = self.process_form(edit_form)
        conversation.set_metadata(metadata)
        conversation.save()


class EndConversationView(ConversationView):
    def post(self, request, conversation):
        conversation.end_conversation()
        messages.add_message(
            request, messages.INFO,
            '%s ended' % (self.conversation_display_name,))
        return self.redirect_to('show', conversation_key=conversation.key)


class MessageSearchResultConversationView(ConversationView):

    def get(self, request, conversation):
        client = ms_client.Client(settings.MESSAGE_STORE_API_URL)
        query = request.GET['q']
        batch_id = request.GET['batch_id']
        direction = request.GET['direction']
        token = request.GET['token']
        delay = float(request.GET.get('delay', 100))
        page = int(request.GET.get('p', 1))
        match_results = ms_client.MatchResult(client, batch_id, direction,
                                                token, page)

        context = {
            'conversation': conversation,
            'query': query,
            'token': token,
            'batch_id': batch_id,
            'message_direction': direction,
            'user_api': request.user_api,
        }
        if match_results.is_in_progress():
            context.update({
                'delay': delay * 1.1,
            })
            return render(request,
                'generic/includes/message-load-results.html', context)

        message_paginator = match_results.paginator

        try:
            message_page = message_paginator.page(page)
        except PageNotAnInteger:
            message_page = message_paginator.page(1)
        except EmptyPage:
            message_page = message_paginator.page(message_paginator.num_pages)

        context.update({
            'message_page': message_page,
            'message_page_range': page_range_window(message_page, 5),
            })
        return render(request,
            'generic/includes/message-list.html', context)


def tf_server_initiated(pool, metadata):
    return metadata.get('server_initiated', False)


def tf_client_initiated(pool, metadata):
    return metadata.get('client_initiated', False)


class ConversationViews(object):
    """Generic conversation view machinery.

    NOTE: This is an early iteration. Please set expectations accordingly.

    Subclass this for your shiny new conversation and setting the appropriate
    attributes and/or add special magic code.

    Individual view classes may be overridden for conversations that are unique
    and special snowflakes by setting the `*_conversation_view` attributes. If
    you need new views, add the appropriate conversation_view attributes and
    implement `.extra_urls()` to build the right URLs.

    The following more general attributes are passed through to each view:

    :param conversation_type:
        The name of this application. Currently needs to be the app submodule
        name. (Mandatory)

    :param conversation_form:
        The conversation form to use. Defaults to `ConversationForm`.

    :param conversation_group_form:
        The conversation group form to use. Defaults to
        `ConversationGroupForm`.

    :param tagpool_filter:
        Filter function for tagpools. It gets set appropriately based on
        `conversation_initiator` if it hasn't been overridden.

    :param conversation_initiator:
        Should be `'server'` for server-initiated-only conversations,
        `'client'` for client-initiated-only conversations or `None` for
        conversations that can be either client-initiated or server-initiated.
        Among other things, this determines the applicable tagpool filter and
        conversation setup flow.

    :param conversation_display_name:
        Used in various places in the UI for messaging. Defaults to
        `'Conversation'`.

    :param edit_conversation_forms:
        If set, the conversation will be editable and form data will be stashed
        in the conversation metadata field. See :class:`EditConversationView`
        for details.

    :param conversation_display_name:
        A dict containing default parameters to send with the conversation
        start command.
    """

    new_conversation_view = NewConversationView
    people_conversation_view = PeopleConversationView
    start_conversation_view = StartConversationView
    show_conversation_view = ShowConversationView
    edit_conversation_view = EditConversationView
    end_conversation_view = EndConversationView
    message_search_result_conversation_view = \
        MessageSearchResultConversationView
    aggregates_conversation_view = AggregatesConversationView
    confirm_conversation_view = ConfirmConversationView

    # These attributes get passed through to the individual view objects.
    conversation_type = None
    conversation_form = ConversationForm
    conversation_group_form = ConversationGroupForm
    tagpool_filter = None
    conversation_initiator = None  # This can be "client", "server" or None.
    conversation_display_name = 'Conversation'
    edit_conversation_forms = None
    conversation_start_params = None

    def mkview(self, name):
        cls = getattr(self, '%s_conversation_view' % (name,))
        if self.tagpool_filter is None:
            self.tagpool_filter = {
                'server': tf_server_initiated,
                'client': tf_client_initiated,
                None: None,
                }[self.conversation_initiator]
        return cls.as_view(
            conversation_type=self.conversation_type,
            conversation_form=self.conversation_form,
            conversation_group_form=self.conversation_group_form,
            tagpool_filter=self.tagpool_filter,
            conversation_initiator=self.conversation_initiator,
            conversation_display_name=self.conversation_display_name,
            edit_conversation_forms=self.edit_conversation_forms,
            conversation_start_params=self.conversation_start_params)

    def mkurl(self, name, regex=None):
        if regex is None:
            regex = r'^(?P<conversation_key>\w+)/%s/' % (name,)
        return url(regex, self.mkview(name), name=name)

    def get_urlpatterns(self):
        urls = [
            self.mkurl('new', r'^new/'),
            self.mkurl('start'),
            self.mkurl('end'),
            self.mkurl('show', r'^(?P<conversation_key>\w+)/$'),
            self.mkurl('message_search_result'),
            self.mkurl('aggregates',
                r'^(?P<conversation_key>\w+)/aggregates\.csv$'),
            self.mkurl('confirm'),
            ] + self.extra_urls()
        if self.conversation_initiator != 'client':
            urls.append(self.mkurl('people'))
        if self.edit_conversation_forms is not None:
            urls.append(self.mkurl('edit'))
        return patterns('', *urls)

    def extra_urls(self):
        return []
