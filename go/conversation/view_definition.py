import csv
import logging
import functools
from StringIO import StringIO
from urllib import urlencode

from django.views.generic import View, TemplateView
from django import forms
from django.shortcuts import redirect, Http404
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from go.vumitools.exceptions import ConversationSendError
from go.token.django_token_manager import DjangoTokenManager
from go.conversation.forms import (ConfirmConversationForm, ReplyToMessageForm,
                                   ConversationDetailForm)
from go.conversation.tasks import export_conversation_messages

logger = logging.getLogger(__name__)


class ConversationViewMixin(object):
    view_name = None
    path_suffix = None
    csrf_exempt = False

    # This is set in the constructor, but the attribute must exist already.
    view_def = None

    def redirect_to(self, name, **kwargs):
        return redirect(self.get_view_url(name, **kwargs))

    def get_view_url(self, view_name, **kwargs):
        return self.view_def.get_view_url(view_name, **kwargs)

    def get_next_view(self, conversation):
        return 'show'


class ConversationTemplateView(ConversationViewMixin, TemplateView):
    template_base = 'conversation'

    def get_template_names(self):
        return [self.get_template_name(self.view_name)]

    def get_template_name(self, name):
        return '%s/%s.html' % (self.template_base, name)


class ConversationApiView(ConversationViewMixin, View):
    pass


class StartConversationView(ConversationApiView):
    view_name = 'start'
    path_suffix = 'start/'

    def post(self, request, conversation):
        # TODO: Better conversation start error handling.
        try:
            conversation.start()
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
        else:
            messages.add_message(request, messages.INFO, '%s started' % (
                self.view_def.conversation_display_name,))
        return self.redirect_to('show', conversation_key=conversation.key)


class ConfirmConversationView(ConversationTemplateView):
    view_name = 'confirm'
    path_suffix = 'confirm/'

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

        action_name = token_data['extra_params'].get('action_name')
        action_data = token_data['extra_params'].get('action_data', {})
        action = self.view_def.get_action(action_name)
        action_view = ConversationActionView(
            view_def=self.view_def, action=action)

        user_token, sys_token = token_manager.parse_full_token(token)
        confirmation_form = ConfirmConversationForm(request.POST)
        success = False
        if confirmation_form.is_valid():
            try:
                if token_manager.delete(user_token):
                    return action_view.perform_action(
                        request, conversation, action_data)
                else:
                    messages.warning("Conversation already confirmed!")
            # TODO: Better exception handling
            except ConversationSendError as error:
                messages.error(request, str(error))
        else:
            messages.error('Invalid confirmation form.')

        return self.render_to_response({
            'form': confirmation_form,
            'conversation': conversation,
            'success': success,
        })


class StopConversationView(ConversationApiView):
    view_name = 'stop'
    path_suffix = 'stop/'

    def post(self, request, conversation):
        conversation.stop_conversation()
        messages.add_message(
            request, messages.INFO, '%s stopped' % (
                self.view_def.conversation_display_name,))
        return self.redirect_to('show', conversation_key=conversation.key)


class ArchiveConversationView(ConversationApiView):
    view_name = 'archive'
    path_suffix = 'archive/'

    def post(self, request, conversation):
        conversation.archive_conversation()
        messages.add_message(
            request, messages.INFO, '%s archived' % (
                self.view_def.conversation_display_name,))
        return redirect(reverse('conversations:index'))


class ShowConversationView(ConversationTemplateView):
    view_name = 'show'
    path_suffix = ''

    def get(self, request, conversation):
        params = {
            'conversation': conversation,
            'is_editable': self.view_def.is_editable,
            'user_api': request.user_api,
            'actions': self.view_def.get_actions(),
        }
        templ = lambda name: self.get_template_name('includes/%s' % (name,))

        if conversation.archived():
            # HACK: This assumes "stopped" and "archived" are equivalent.
            params['button_template'] = templ('ended-button')
        elif conversation.running():
            params['button_template'] = templ('end-button')
        else:
            # TODO: Figure out better state management.
            params['button_template'] = templ('next-button')
            params['next_url'] = self.get_view_url(
                self.get_next_view(conversation),
                conversation_key=conversation.key)
        return self.render_to_response(params)

    @staticmethod
    def send_one_off_reply(user_api, conversation, in_reply_to, content):
        inbound_message = user_api.api.mdb.get_inbound_message(in_reply_to)
        if inbound_message is None:
            logger.info('Replying to an unknown message: %s' % (in_reply_to,))

        conversation.dispatch_command(
            'send_message', user_api.user_account_key, conversation.key,
            command_data={
                "batch_id": conversation.get_latest_batch_key(),
                "conversation_key": conversation.key,
                "to_addr": inbound_message['from_addr'],
                "content": content,
                "msg_options": {'in_reply_to': in_reply_to},
           }
        )

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
                self.send_one_off_reply(request.user_api, conversation,
                                        in_reply_to, content)
                messages.info(request, 'Reply scheduled for sending.')
            else:
                messages.error(request,
                    'Something went wrong. Please try again.')
        return self.redirect_to('show', conversation_key=conversation.key)


class EditConversationDetailView(ConversationTemplateView):
    """view for editing conversation details such as name & description
    """

    view_name = 'edit_detail'
    path_suffix = 'edit_detail/'
    edit_form = ConversationDetailForm

    def _render_form(self, request, conversation, form):
        return self.render_to_response({
            'conversation': conversation,
            'edit_form_media': sum([form.media], forms.Media()),
            'edit_form': form,
        })

    def make_form(self, edit_form, conversation):
        return self.edit_form(initial={
            'name': conversation.name,
            'description': conversation.description,
        })

    def process_form(self, request, conversation):
        form = self.edit_form(request.POST)
        if not form.is_valid():
            return self._render_forms(request, conversation, form)

        # NOTE: we're dealing with a conversation wrapper here so set the
        #       internal `c` object's attributes.
        conversation.c.name = form.cleaned_data['name']
        conversation.c.description = form.cleaned_data['description']
        conversation.c.extra_endpoints = self.view_def.get_endpoints(
            conversation.config)

        conversation.save()

    def get(self, request, conversation):
        form = self.make_form(self.edit_form, conversation)
        return self._render_form(request, conversation, form)

    def post(self, request, conversation):
        response = self.process_form(request, conversation)
        if response is not None:
            return response

        return self.redirect_to(self.get_next_view(conversation),
                                conversation_key=conversation.key)


class EditConversationView(ConversationTemplateView):
    """View for editing conversation data.

    Subclass this and set :attr:`edit_forms` to a list of tuples
    of the form `('key', FormClass)`.

    The `key` should be a key into the conversation's metadata field. If `key`
    is `None`, the whole of the metadata field will be used.

    If the default behaviour is insufficient or problematic, implement
    :meth:`make_forms` and :meth:`process_forms`. These are the only two
    methods that look at :attr:`edit_forms`.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    edit_forms = ()

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
        config = conversation.get_config()
        return [self.make_form(key, edit_form, config)
                for key, edit_form in self.edit_forms]

    def process_form(self, form):
        if hasattr(form, 'to_metadata'):
            return form.to_metadata()
        return form.cleaned_data

    def process_forms(self, request, conversation):
        config = conversation.get_config()
        edit_forms_with_keys = [
            (key, edit_form_cls(request.POST, prefix=key))
            for key, edit_form_cls in self.edit_forms]
        edit_forms = [edit_form for _key, edit_form in edit_forms_with_keys]

        for key, edit_form in edit_forms_with_keys:
            # Is this a good idea?
            if not edit_form.is_valid():
                return self._render_forms(request, conversation, edit_forms)
            config[key] = self.process_form(edit_form)
        conversation.set_config(config)
        conversation.save()


def check_action_is_enabled(f):
    """Decorator to check that the action is not disabled.

    Redirections to 'show' conversation with an appropriate message
    if the action is disabled. Calls the original function otherwise.

    Only wraps functions of the form
    `f(request, conversation, *args, **kw)`.
    """
    @functools.wraps(f)
    def wrapper(self, request, conversation, *args, **kw):
        disabled = self.action.is_disabled()
        if disabled is not None:
            messages.warning(request, 'Action disabled: %s' % (disabled,))
            return self.redirect_to(
                'show', conversation_key=conversation.key)
        return f(self, request, conversation, *args, **kw)
    return wrapper


class ConversationActionView(ConversationTemplateView):
    """View for performing an arbitrary conversation action.

    This is a special case, and is therefore handled differently.
    """
    view_name = 'action'

    # This is set in the constructor, but the attribute must exist already.
    action = None

    def _render_form(self, request, conversation, form):
        return self.render_to_response({
            'conversation': conversation,
            'form': form,
            'action_display_name': self.action.action_display_name,
        })

    @check_action_is_enabled
    def get(self, request, conversation):
        form_cls = self.view_def.get_action_form(self.action.action_name)
        if form_cls is None:
            # We have no form, so assume we're just redirecting elsewhere.
            return self._action_done(request, conversation)
        return self._render_form(request, conversation, form_cls)

    @check_action_is_enabled
    def post(self, request, conversation):
        action_data = {}
        form_cls = self.view_def.get_action_form(self.action.action_name)
        if form_cls is not None:
            form = form_cls(request.POST)
            if not form.is_valid():
                return self._render_form(request, conversation, form)
            action_data = form.cleaned_data

        if self.action.needs_confirmation:
            user_account = request.user_api.get_user_account()
            # TODO: Rename this field
            if user_account.confirm_start_conversation:
                return self._confirm_action(
                    request, conversation, user_account, action_data)

        return self.perform_action(request, conversation, action_data)

    @check_action_is_enabled
    def perform_action(self, request, conversation, action_data):
        self.action.perform_action(action_data)
        messages.info(request, 'Action successful: %s!' % (
            self.action.action_display_name,))
        return self._action_done(request, conversation)

    def _action_done(self, request, conversation):
        next_view = self.get_next_view(conversation)
        if self.action.redirect_to is not None:
            next_view = self.action.redirect_to
        return self.redirect_to(next_view, conversation_key=conversation.key)

    def _confirm_action(self, request, conv, user_account, action_data):
        # The URL the user will be redirected to post-confirmation
        redirect_to = self.get_view_url('confirm', conversation_key=conv.key)
        # The token to be sent.
        params = {
            'action_name': self.action.action_name,
            'action_data': action_data,
        }

        token_manager = DjangoTokenManager(request.user_api.api.token_manager)
        token = token_manager.generate(redirect_to, user_id=request.user.id,
                                       extra_params=params)
        conv.send_token_url(
            token_manager.url_for_token(token), user_account.msisdn,
            acquire_tag=False)
        messages.info(request, 'Confirmation request sent.')
        return self.redirect_to('show', conversation_key=conv.key)


class AggregatesConversationView(ConversationTemplateView):
    view_name = 'aggregates'
    path_suffix = 'aggregates.csv'

    def get(self, request, conversation):
        sio = StringIO()
        writer = csv.writer(sio)
        direction = request.GET.get('direction', 'inbound')
        writer.writerows(conversation.get_aggregate_count(direction))
        return HttpResponse(sio.getvalue(),
            content_type='text/csv; charset=utf-8')


class EditConversationGroupsView(ConversationTemplateView):
    view_name = 'edit_groups'
    path_suffix = 'edit_groups/'

    def _render_groups(self, request, conversation):
        groups = sorted(request.user_api.list_groups(),
                        key=lambda group: group.created_at,
                        reverse=True)

        selected_groups = list(group.key for group
                               in conversation.get_groups())

        for group in groups:
            if group.key in selected_groups:
                group.selected = True

        query = request.GET.get('query', '')
        p = request.GET.get('p', 1)

        paginator = Paginator(groups, 15)
        try:
            page = paginator.page(p)
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

        pagination_params = urlencode({
            'query': query,
        })

        return self.render_to_response({
            'paginator': paginator,
            'page': page,
            'pagination_params': pagination_params,
            'conversation': conversation,
        })

    def get(self, request, conversation):
        return self._render_groups(request, conversation)

    def post(self, request, conversation):
        group_keys = request.POST.getlist('group')
        conversation.groups.clear()
        for group_key in group_keys:
            conversation.add_group(group_key)
        conversation.save()

        return self.redirect_to(self.get_next_view(conversation),
                                conversation_key=conversation.key)


class ConversationViewDefinitionBase(object):
    """Definition of conversation UI.

    NOTE: This is an early iteration. Please set expectations accordingly.

    Subclass this for your shiny new conversation and set the appropriate
    attributes and/or add special magic code.
    """

    # Override these params in your app-specific subclass.
    extra_views = ()
    edit_view = None
    action_forms = {}

    # This doesn't include ConversationActionView because that's special.
    DEFAULT_CONVERSATION_VIEWS = (
        ShowConversationView,
        EditConversationDetailView,
        EditConversationGroupsView,
        StartConversationView,
        ConfirmConversationView,
        StopConversationView,
        ArchiveConversationView,
        AggregatesConversationView,
    )

    def __init__(self, conv_def):
        self._conv_def = conv_def

        self._views = list(self.DEFAULT_CONVERSATION_VIEWS)
        if self.edit_view is not None:
            self._views.append(self.edit_view)
        self._views.extend(self.extra_views)

        self._view_mapping = {}
        self._path_suffix_mapping = {}
        for view in self._views:
            self._view_mapping[view.view_name] = view
            self._path_suffix_mapping[view.path_suffix] = view

    @property
    def conversation_display_name(self):
        return self._conv_def.conversation_display_name

    @property
    def extra_static_endpoints(self):
        return self._conv_def.extra_static_endpoints

    def get_endpoints(self, config):
        endpoints = list(self.extra_static_inbound_endpoints)
        for endpoint in self._conv_def.configured_endpoints(config):
            if (endpoint != 'default') and (endpoint not in endpoints):
                endpoints.append(endpoint)
        return endpoints

    @property
    def is_editable(self):
        return self.edit_view is not None

    def get_actions(self):
        return self._conv_def.get_actions()

    def get_action(self, action_name):
        for action in self.get_actions():
            if action.action_name == action_name:
                return action
            raise ValueError("Action not found: %s" % (action_name,))

    def get_action_form(self, action_name):
        """Returns a Django form for setting up the action or ``None``."""
        return self.action_forms.get(action_name, None)

    def get_view_url(self, view_name, **kwargs):
        kwargs['path_suffix'] = self._view_mapping[view_name].path_suffix
        return reverse('conversations:conversation', kwargs=kwargs)

    def get_view(self, path_suffix):
        if path_suffix not in self._path_suffix_mapping:
            raise Http404
        view_cls = self._path_suffix_mapping[path_suffix]
        view = view_cls.as_view(view_def=self)
        if view_cls.csrf_exempt:
            view = csrf_exempt(view)
        return view

    def get_action_view(self, action_name):
        for action in self._conv_def.get_actions():
            if action.action_name == action_name:
                return ConversationActionView.as_view(
                    view_def=self, action=action)
        raise Http404
