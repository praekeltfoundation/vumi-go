from urllib import urlencode

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator

from go.conversation.forms import NewConversationForm
from go.channel.forms import NewChannelForm
from go.base.utils import (
    get_conversation_view_definition, conversation_or_404)

import logging
logger = logging.getLogger(__name__)


class BaseWizardView(TemplateView):
    template_base = 'wizard_views'
    view_name = None

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(BaseWizardView, self).dispatch(*args, **kwargs)

    def get_template_names(self):
        return ['%s/%s.html' % (self.template_base, self.view_name)]


class WizardCreateView(BaseWizardView):
    view_name = 'wizard_1_create'

    def _render(self, request, wizard_form=None, conversation_form=None,
                channel_form=None, router_form=None):
        return self.render_to_response({
            'conversation_form': (conversation_form or
                                  NewConversationForm(request.user_api)),
            'channel_form': (channel_form or NewChannelForm(request.user_api)),
        })

    def get(self, request):
        return self._render(request)

    def post(self, request):
        # TODO: Reuse new conversation/channel view logic here.
        conv_form = NewConversationForm(request.user_api, request.POST)
        chan_form = NewChannelForm(request.user_api, request.POST)

        forms_to_validate = [conv_form, chan_form]
        forms_valid = [form.is_valid() for form in forms_to_validate]
        if not all(forms_valid):
            logger.info("Validation failed: %s" % (
                [frm.errors for frm in forms_to_validate],))
            return self._render(request, conversation_form=conv_form,
                                channel_form=chan_form)

        # Create conversation
        view_def, conv = self._create_conversation(
            request, conv_form.cleaned_data)

        self._handle_new_channel(request, chan_form.cleaned_data, conv)

        messages.info(request, 'Conversation created successfully.')
        if view_def.is_editable:
            return redirect(view_def.get_view_url(
                'edit', conversation_key=conv.key))
        else:
            return redirect(view_def.get_view_url(
                'show', conversation_key=conv.key))

    def _handle_new_channel(self, request, chan_data, conv):
        channel_data = tuple(chan_data['channel'].split(':', 1))
        if channel_data[1]:
            tag = request.user_api.acquire_specific_tag(channel_data)
        else:
            tag = request.user_api.acquire_tag(channel_data[0])
        channel = request.user_api.get_channel(tag)

        self._setup_basic_routing(request, conv, channel)

    def _create_conversation(self, request, conv_data):
        conversation_type = conv_data['conversation_type']

        name = conv_data['name']
        description = conv_data['description']
        view_def = get_conversation_view_definition(conversation_type)
        config = view_def._conv_def.get_default_config(name, description)

        conversation = request.user_api.new_conversation(
            conversation_type, name=name,
            description=description, config=config,
            extra_endpoints=list(view_def.extra_static_endpoints),
        )
        return view_def, conversation

    def _setup_basic_routing(self, request, conv, channel):
        user_account = request.user_api.get_user_account()
        routing_table = request.user_api.get_routing_table(user_account)

        conv_conn = conv.get_connector()
        tag_conn = channel.get_connector()
        routing_table.add_entry(conv_conn, "default", tag_conn, "default")
        routing_table.add_entry(tag_conn, "default", conv_conn, "default")
        user_account.save()


@login_required
def contacts(request, conversation_key):
    conversation = conversation_or_404(request.user_api, conversation_key)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'draft':
            # save and go back to list.
            return redirect('conversations:index')

        group_keys = request.POST.getlist('group')

        # TODO: Remove all groups
        for group_key in group_keys:
            conversation.add_group(group_key)
        conversation.save()

        return redirect('conversations:conversation',
                        conversation_key=conversation.key, path_suffix='')

    groups = sorted(request.user_api.list_groups(),
                    key=lambda group: group.created_at,
                    reverse=True)

    selected_groups = list(group.key for group in conversation.get_groups())

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

    return render(request, 'wizard_views/wizard_3_contacts.html', {
        'paginator': paginator,
        'page': page,
        'pagination_params': pagination_params,
        'conversation_key': conversation_key,
        'conversation': conversation,
    })


# TODO: Something sensible with the pricing view.
@login_required
def pricing(request):
    return render(request, 'conversations/pricing.html', {
    })
