import csv
import datetime
import json
import logging
import functools
import re
import sys
import urllib
from StringIO import StringIO
from collections import defaultdict

from django.views.generic import View, TemplateView
from django import forms
from django.shortcuts import redirect, Http404
from django.core.exceptions import SuspiciousOperation
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from vumi.message import parse_vumi_date

from go.base.utils import page_range_window, sendfile
from go.base.decorators import render_exception
from go.vumitools.exceptions import ConversationSendError
from go.token.django_token_manager import DjangoTokenManager
from go.conversation.forms import (ConfirmConversationForm, ReplyToMessageForm,
                                   ConversationDetailForm)
from go.conversation.utils import PagedMessageCache
from go.dashboard.dashboard import Dashboard, ConversationReportsLayout

import go.conversation.settings as conversation_settings

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

        params = token_data['extra_params']
        action_name = params.get('action_display_name')
        action_details = params.get('action_data').get('display', {})

        return self.render_to_response({
            'success': False,
            'conversation': conversation,
            'action_name': action_name,
            'action_details': action_details,
            'form': ConfirmConversationForm(initial={'token': token}),
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
            'success': success,
            'conversation': conversation,
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


class ExportMessageView(ConversationApiView):
    view_name = 'export_messages'
    path_suffix = 'export_messages/'

    PRESET_DAYS_RE = re.compile("^[0-9]+d$")
    CUSTOM_DATE_RE = re.compile("^[0-9]+/[0-9]+/[0-9]+")

    def _check_option(self, field, opt, values):
        if opt not in values:
            raise SuspiciousOperation("Invalid %s: '%s'." % (field, opt))
        return opt

    def _parse_date_preset(self, preset):
        if preset == "all":
            return None, None
        if self.PRESET_DAYS_RE.match(preset):
            days = int(preset[:-1])
            start_time = (
                datetime.datetime.utcnow() - datetime.timedelta(days=days))
            return start_time, None
        raise SuspiciousOperation("Invalid date-preset: '%s'." % (preset,))

    def _parse_custom_date(self, field, custom_date):
        if custom_date is None:
            return None
        if self.CUSTOM_DATE_RE.match(custom_date):
            day, month, year = [int(part) for part in custom_date.split("/")]
            try:
                return datetime.datetime(year, month, day, tzinfo=timezone.utc)
            except ValueError:
                pass  # year, month or day out of range
        raise SuspiciousOperation(
            "Invalid %s: '%s'." % (field, custom_date))

    def _format_custom_date_part(self, date, default):
        if date is None:
            return default
        return date.strftime('%Y%m%d')

    def _format_custom_date_filename(self, start_date, end_date):
        if start_date is None and end_date is None:
            return "all"
        return "-".join([
            self._format_custom_date_part(start_date, 'until'),
            self._format_custom_date_part(end_date, 'now'),
        ])

    @render_exception(
        SuspiciousOperation, 400,
        "Oops. Something didn't look right with your message export request.")
    def post(self, request, conversation):
        export_format = self._check_option(
            'format', request.POST.get('format'), ['csv', 'json'])

        direction = self._check_option(
            'direction',
            request.POST.get('direction'), ['inbound', 'outbound'])

        date_preset = self._check_option(
            'date-preset', request.POST.get('date-preset'),
            ['all', '1d', '7d', '30d', None])

        if date_preset is not None:
            start_date, end_date = self._parse_date_preset(date_preset)
            filename_date = date_preset
        else:
            start_date = self._parse_custom_date(
                'date-from', request.POST.get('date-from'))
            end_date = self._parse_custom_date(
                'date-to', request.POST.get('date-to'))
            filename_date = self._format_custom_date_filename(
                start_date, end_date)

        url_params = {}
        if start_date is not None:
            url_params['start'] = start_date.isoformat()
        if end_date is not None:
            url_params['end'] = end_date.isoformat()

        url = '/message_store_exporter/%s/%s.%s' % (
            conversation.batch.key, direction, export_format)
        if url_params:
            url += '?' + urllib.urlencode(url_params)

        return sendfile(url, buffering=False, filename='%s-%s-%s.%s' % (
            conversation.key, direction, filename_date, export_format))


class MessageListView(ConversationTemplateView):
    view_name = 'message_list'
    path_suffix = 'message_list/'

    def get(self, request, conversation):
        """
        Render the messages sent & received for this conversation.

        Takes the following query parameters:

        :param str direction:
            Either 'inbound' or 'outbound', defaults to 'inbound'
        :param int page:
            The page to display for the pagination.
        :param str query:
            The query string to search messages for in the batch's inbound
            messages.
            NOTE: This is currently unused.
        """
        direction = request.GET.get('direction', 'inbound')
        page = request.GET.get('p', 1)

        batch_id = conversation.batch.key

        def add_event_status(msg):
            if not conversation_settings.ENABLE_EVENT_STATUSES_IN_MESSAGE_LIST:
                msg.event_status = "-"
                return msg
            msg.event_status = u"Sending"
            get_event_info = conversation.mdb.message_event_keys_with_statuses
            for event_id, _, event_type in get_event_info(msg["message_id"]):
                if event_type == u"ack":
                    msg.event_status = u"Accepted"
                    break
                if event_type == u"nack":
                    event = conversation.mdb.get_event(event_id)
                    msg.event_status = u"Rejected: %s" % (
                        event["nack_reason"],)
                    break
            return msg

        def get_sent_messages(start, stop):
            return [add_event_status(m)
                    for m in conversation.sent_messages_in_cache(start, stop)]

        # Paginator starts counting at 1 so 0 would also be invalid
        inbound_message_paginator = Paginator(PagedMessageCache(
            conversation.count_inbound_messages(),
            lambda start, stop: conversation.received_messages_in_cache(
                start, stop)), 20)
        outbound_message_paginator = Paginator(PagedMessageCache(
            conversation.count_outbound_messages(),
            lambda start, stop: get_sent_messages(start, stop)), 20)

        tag_context = {
            'batch_id': batch_id,
            'conversation': conversation,
            'inbound_message_paginator': inbound_message_paginator,
            'outbound_message_paginator': outbound_message_paginator,
            'inbound_uniques_count': conversation.count_inbound_uniques(),
            'outbound_uniques_count': conversation.count_outbound_uniques(),
            'message_direction': direction,
        }

        if direction == 'inbound':
            message_paginator = inbound_message_paginator
        else:
            message_paginator = outbound_message_paginator

        try:
            message_page = message_paginator.page(page)
        except PageNotAnInteger:
            message_page = message_paginator.page(1)
        except EmptyPage:
            message_page = message_paginator.page(message_paginator.num_pages)

        tag_context.update({
            'message_page': message_page,
            'message_page_range': page_range_window(message_page, 5),
        })
        return self.render_to_response(tag_context)

    @staticmethod
    def send_one_off_reply(user_api, conversation, in_reply_to, content):
        inbound_message = user_api.api.mdb.get_inbound_message(in_reply_to)
        if inbound_message is None:
            logger.info('Replying to an unknown message: %s' % (in_reply_to,))

        conversation.dispatch_command(
            'send_message', user_api.user_account_key, conversation.key,
            command_data={
                "batch_id": conversation.batch.key,
                "conversation_key": conversation.key,
                "to_addr": inbound_message['from_addr'],
                "content": content,
                "msg_options": {'in_reply_to': in_reply_to},
            }
        )

    def post(self, request, conversation):
        if '_send_one_off_reply' in request.POST:
            form = ReplyToMessageForm(request.POST)
            if form.is_valid():
                in_reply_to = form.cleaned_data['in_reply_to']
                content = form.cleaned_data['content']
                self.send_one_off_reply(request.user_api, conversation,
                                        in_reply_to, content)
                messages.info(request, 'Reply scheduled for sending.')
            else:
                messages.error(
                    request, 'Something went wrong. Please try again.')
        return self.redirect_to(
            'message_list', conversation_key=conversation.key)


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
            return self._render_form(request, conversation, form)

        # NOTE: we're dealing with a conversation wrapper here so set the
        #       internal `c` object's attributes.
        conversation.c.name = form.cleaned_data['name']
        conversation.c.description = form.cleaned_data['description']

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

    The `key` should be a key into the conversation's config field. If `key`
    is `None`, the whole of the config field will be used.

    If the default behaviour is insufficient or problematic, implement
    :meth:`make_forms` and :meth:`process_forms`. These are the only two
    methods that look at :attr:`edit_forms`.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    edit_forms = ()
    help_template = None

    @staticmethod
    def sum_media(form_list):
        return sum((f.media for f in form_list), forms.Media())

    def _render_forms(self, request, conversation, edit_forms):
        return self.render_to_response({
            'conversation': conversation,
            'edit_forms_media': self.sum_media(edit_forms),
            'edit_forms': edit_forms,
            'help_template': self.help_template,
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

    def make_form(self, key, form, config):
        if key is None:
            data = config
        else:
            data = config.get(key, {})
        if hasattr(form, 'initial_from_config'):
            data = form.initial_from_config(data)
        return form(prefix=key, initial=data)

    def make_forms(self, conversation):
        config = conversation.get_config()
        return [self.make_form(key, edit_form, config)
                for key, edit_form in self.edit_forms]

    def make_forms_dict(self, conversation):
        config = conversation.get_config()
        return dict((key, self.make_form(key, edit_form, config))
                    for key, edit_form in self.edit_forms)

    def process_form(self, form):
        if hasattr(form, 'to_config'):
            return form.to_config()
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
            if key is None:
                config = self.process_form(edit_form)
            else:
                config[key] = self.process_form(edit_form)

        user_account = request.user_api.get_user_account()
        self.view_def._conv_def.update_config(user_account, config)
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


class FallbackEditConversationView(ConversationApiView):
    """A fallback 'edit' view that redirects to the 'show' view.

    For use on conversation types that have no custom edit
    view to prevent 404s from occurring if another part of
    the user interface directs a person to the edit view.
    """
    view_name = 'edit'
    path_suffix = 'edit/'

    def get(self, request, conversation):
        return self.redirect_to('show', conversation_key=conversation.key)


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
            'action': self.action,
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
        action_data = {'display': {}}
        form_cls = self.view_def.get_action_form(self.action.action_name)
        if form_cls is not None:
            form = form_cls(request.POST)
            if not form.is_valid():
                return self._render_form(request, conversation, form)
            action_data = form.cleaned_data
            action_data['display'] = dict(
                (form[k].label, v)
                for k, v in action_data.iteritems())

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
            'action_data': action_data,
            'action_name': self.action.action_name,
            'action_display_name': self.action.action_display_name,
        }

        token_manager = DjangoTokenManager(request.user_api.api.token_manager)
        token = token_manager.generate(redirect_to, user_id=request.user.id,
                                       extra_params=params)

        conv.send_token_url(
            token_manager.url_for_token(token), user_account.msisdn)
        messages.info(request, 'Confirmation request sent.')
        return self.redirect_to('show', conversation_key=conv.key)


class AggregatesConversationView(ConversationTemplateView):
    view_name = 'aggregates'
    path_suffix = 'aggregates.csv'

    def get(self, request, conversation):
        sio = StringIO()
        writer = csv.writer(sio)
        direction = request.GET.get('direction', 'inbound')
        writer.writerows(self.get_aggregate_counts(conversation, direction))
        return HttpResponse(
            sio.getvalue(), content_type='text/csv; charset=utf-8')

    def get_aggregate_counts(self, conv, direction):
        """
        Get aggregated total count of messages handled bucketed per day.
        """
        message_callback = {
            'inbound': conv.mdb.batch_inbound_keys_with_timestamps,
            'outbound': conv.mdb.batch_outbound_keys_with_timestamps,
        }.get(direction, conv.mdb.batch_inbound_keys_with_timestamps)

        aggregates = defaultdict(int)
        index_page = message_callback(conv.batch.key)
        while index_page is not None:
            for key, timestamp in index_page:
                timestamp = parse_vumi_date(timestamp)
                aggregates[timestamp.date()] += 1
            index_page = index_page.next_page()

        return sorted(aggregates.items())


class EditConversationGroupsView(ConversationTemplateView):
    view_name = 'edit_groups'
    path_suffix = 'edit_groups/'

    def _render_groups(self, request, conversation):
        groups = sorted(request.user_api.list_groups(),
                        key=lambda group: group.created_at,
                        reverse=True)

        selected_groups = set(group.key for group in conversation.get_groups())

        model_data = {
            'key': conversation.key,
            'groups': [{
                'key': group.key,
                'name': group.name,
                'urls': {
                    'show': reverse(
                        'contacts:group',
                        kwargs={'group_key': group.key}),
                },
                'inConversation': group.key in selected_groups,
            } for group in groups],
            'urls': {
                'show': self.get_view_url(
                    'show',
                    conversation_key=conversation.key)
            },
        }

        return self.render_to_response({
            'conversation': conversation,
            'model_data': json.dumps(model_data),
            'contact_store': request.user_api.contact_store,
        })

    def get(self, request, conversation):
        return self._render_groups(request, conversation)

    def put(self, request, conversation):
        data = json.loads(request.body)
        group_keys = [d['key'] for d in data['groups']]

        conversation.groups.clear()
        for group_key in group_keys:
            conversation.add_group(group_key)
        conversation.save()

        return HttpResponse(
            json.dumps({'success': True}),
            content_type="application/json")


class ConversationReportsView(ConversationTemplateView):
    view_name = 'reports'
    path_suffix = 'reports/'

    def build_layout(self, conversation):
        """
        Returns a conversation's dashboard widget data.
        Override to specialise dashboard building.
        """

        metrics = self.view_def.get_metrics()
        return ConversationReportsLayout(conversation, [{
            'type': 'diamondash.widgets.lvalue.LValueWidget',
            'time_range': '1d',
            'name': 'Messages Sent (24h)',
            'target': metrics.get('messages_sent').get_target_spec(),
        }, {
            'type': 'diamondash.widgets.lvalue.LValueWidget',
            'time_range': '1d',
            'name': 'Messages Received (24h)',
            'target': metrics.get('messages_received').get_target_spec(),
        }, 'new_row', {
            'type': 'diamondash.widgets.graph.GraphWidget',
            'name': 'Messages Sent and Received (24h)',
            'width': 6,
            'time_range': '24h',
            'bucket_size': '15m',
            'metrics': [{
                'name': 'Messages Sent',
                'target': metrics.get('messages_sent').get_target_spec(),
            }, {
                'name': 'Messages Received',
                'target': metrics.get('messages_received').get_target_spec(),
            }]
        }, {
            'type': 'diamondash.widgets.graph.GraphWidget',
            'name': 'Messages Sent and Received (30d)',
            'width': 6,
            'time_range': '30d',
            'bucket_size': '1d',
            'metrics': [{
                'name': 'Messages Sent',
                'target': metrics.get('messages_sent').get_target_spec(),
            }, {
                'name': 'Messages Received',
                'target': metrics.get('messages_received').get_target_spec(),
            }]
        }])

    def on_error(self, e, exc_info):
        """
        Hook for doing things when a errors are encountered while parsing the
        dashboard layout and syncing the dashboard with diamondash. Logs
        the error by default.
        """
        logger.error(e, exc_info=exc_info)

    def get(self, request, conversation):
        try:
            # build the dashboard
            name = "go.conversations.%s" % conversation.key
            layout = self.build_layout(conversation)
            dashboard = Dashboard(name, layout)

            # give the dashboard to diamondash
            dashboard.sync()
            dashboard_config = json.dumps(dashboard.get_config())
        except Exception, e:
            self.on_error(e, sys.exc_info())
            dashboard_config = None

        return self.render_to_response({
            'conversation': conversation,
            'dashboard_config': dashboard_config,
        })


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
        MessageListView,
        ExportMessageView,
        EditConversationDetailView,
        EditConversationGroupsView,
        StartConversationView,
        ConfirmConversationView,
        StopConversationView,
        ArchiveConversationView,
        AggregatesConversationView,
        ConversationReportsView
    )

    def __init__(self, conv_def):
        self._conv_def = conv_def

        self._views = list(self.DEFAULT_CONVERSATION_VIEWS)
        if self.edit_view is not None:
            self._views.append(self.edit_view)
        else:
            self._views.append(FallbackEditConversationView)
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
        return self._conv_def.get_endpoints(config)

    @property
    def is_editable(self):
        return self.edit_view is not None

    def get_metrics(self):
        return self._conv_def.get_metrics()

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
