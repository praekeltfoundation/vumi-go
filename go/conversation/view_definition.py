import csv
import logging
from StringIO import StringIO

from django.views.generic import View, TemplateView
from django import forms
from django.shortcuts import redirect, Http404
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from go.vumitools.exceptions import ConversationSendError
from go.token.django_token_manager import DjangoTokenManager
from go.conversation.forms import ConfirmConversationForm, ReplyToMessageForm
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
            conversation.new_start()
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

        [tag] = conversation.get_tags()
        msg_options = conversation.make_message_options(tag)
        msg_options['in_reply_to'] = in_reply_to
        conversation.dispatch_command(
            'send_message', user_api.user_account_key, conversation.key,
            command_data={
                "batch_id": conversation.get_latest_batch_key(),
                "conversation_key": conversation.key,
                "to_addr": inbound_message['from_addr'],
                "content": content,
                "msg_options": msg_options,
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


class EditConversationView(ConversationTemplateView):
    """View for editing conversation data.

    Subclass this and set :attr:`edit_conversation_forms` to a list of tuples
    of the form `('key', FormClass)`.

    The `key` should be a key into the conversation's metadata field. If `key`
    is `None`, the whole of the metadata field will be used.

    If the default behaviour is insufficient or problematic, implement
    :meth:`make_forms` and :meth:`process_forms`. These are the only two
    methods that look at :attr:`edit_conversation_forms`.
    """
    view_name = 'edit'
    path_suffix = 'edit/'

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
        edit_forms = self.view_def.edit_conversation_forms
        return [self.make_form(key, edit_form, config)
                for key, edit_form in edit_forms]

    def process_form(self, form):
        if hasattr(form, 'to_metadata'):
            return form.to_metadata()
        return form.cleaned_data

    def process_forms(self, request, conversation):
        config = conversation.get_config()
        edit_forms = self.view_def.edit_conversation_forms
        edit_forms_with_keys = [
            (key, edit_form_cls(request.POST, prefix=key))
            for key, edit_form_cls in edit_forms]
        edit_forms = [edit_form for _key, edit_form in edit_forms_with_keys]

        for key, edit_form in edit_forms_with_keys:
            # Is this a good idea?
            if not edit_form.is_valid():
                return self._render_forms(request, conversation, edit_forms)
            config[key] = self.process_form(edit_form)
        conversation.set_config(config)
        conversation.save()


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

    def get(self, request, conversation):
        form_cls = self.view_def.get_action_form(self.action.action_name)
        if form_cls is None:
            # We have no form, so assume we're just redirecting elsewhere.
            return self._action_done(request, conversation)
        return self._render_form(request, conversation, form_cls)

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


class ConversationViewDefinitionBase(object):
    """Definition of conversation UI.

    NOTE: This is an early iteration. Please set expectations accordingly.

    Subclass this for your shiny new conversation and set the appropriate
    attributes and/or add special magic code.

    The following more general attributes are passed through to each view:

    :param edit_conversation_forms:
        If set, the conversation will be editable and form data will be stashed
        in the conversation metadata field. See :class:`EditConversationView`
        for details.
    """

    # Override these params in your app-specific subclass.
    extra_views = ()
    action_forms = {}
    edit_conversation_forms = None  # TODO: Better thing than this.

    # This doesn't include ConversationActionView because that's special.
    DEFAULT_CONVERSATION_VIEWS = (
        ShowConversationView,
        EditConversationView,
        StartConversationView,
        ConfirmConversationView,
        StopConversationView,
        ArchiveConversationView,
        AggregatesConversationView,
    )

    def __init__(self, conv_def):
        self._conv_def = conv_def

        self._views = list(self.DEFAULT_CONVERSATION_VIEWS)
        if self.edit_conversation_forms is None:
            self._views.remove(EditConversationView)
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
    def is_editable(self):
        return self.edit_conversation_forms is not None

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
