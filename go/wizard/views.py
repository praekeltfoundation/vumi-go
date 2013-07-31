from urllib import urlencode

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator

from go.wizard.forms import Wizard1CreateForm
from go.conversation.forms import NewConversationForm
from go.channel.forms import NewChannelForm
from go.base.utils import (
    get_conversation_view_definition, conversation_or_404,
    get_router_view_definition)
from go.vumitools.account import RoutingTableHelper, GoConnector


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

    def get(self, request):
        return self.render_to_response({
            'wizard_form': Wizard1CreateForm(),
            'conversation_form': NewConversationForm(request.user_api),
            'channel_form': NewChannelForm(request.user_api),
        })

    def post(self, request):
        # TODO: Reuse new conversation/channel view logic here.
        conv_form = NewConversationForm(request.user_api, request.POST)
        chan_form = NewChannelForm(request.user_api, request.POST)
        wiz_form = Wizard1CreateForm(request.POST)

        if not all(frm.is_valid() for frm in [conv_form, chan_form, wiz_form]):
            # TODO: Better validation.
            logger.info("Validation failed: %r %r" % (
                conv_form.errors, chan_form.errors))
            return self.get(request)

        # Create channel
        tag = self._create_channel(request, chan_form.cleaned_data)

        # Create conversation
        view_def, conversation = self._create_conversation(
            request, conv_form.cleaned_data)
        messages.info(request, 'Conversation created successfully.')

        # Set up routing
        keyword = wiz_form.cleaned_data['keyword']
        if keyword:
            # Create router
            endpoint, router = self._create_keyword_router(
                request, keyword, ':'.join(tag))
            self._setup_keyword_routing(
                request, conversation, tag, router, endpoint)
        else:
            self._setup_basic_routing(request, conversation, tag)

        if view_def.is_editable:
            return redirect(view_def.get_view_url(
                'edit', conversation_key=conversation.key))
        else:
            return redirect(view_def.get_view_url(
                'show', conversation_key=conversation.key))

    def _create_channel(self, request, channel_data):
        # Create channel
        pool, tag = channel_data['channel'].split(':')
        if tag:
            return request.user_api.acquire_specific_tag((pool, tag))
        else:
            return request.user_api.acquire_tag(pool)

    def _create_conversation(self, request, conv_data):
        conversation_type = conv_data['conversation_type']

        view_def = get_conversation_view_definition(conversation_type)
        conversation = request.user_api.new_conversation(
            conversation_type, name=conv_data['name'],
            description=conv_data['description'], config={},
            extra_endpoints=list(view_def.extra_static_endpoints),
        )
        return view_def, conversation

    def _create_keyword_router(self, request, keyword, channel_name):
        # TODO: Avoid duplicating stuff we already do elsewhere.
        view_def = get_router_view_definition('keyword', None)
        # TODO: Validate keyword?
        endpoint = 'keyword_%s' % (keyword.lower(),)
        config = {'keyword_endpoint_mapping': {keyword: endpoint}}
        router = request.user_api.new_router(
            router_type=u'keyword', name=u'Keywords for %s' % (channel_name,),
            description=u'Keyword router for %s' % (channel_name,),
            config=config,
            extra_outbound_endpoints=view_def.get_outbound_endpoints(config),
        )
        return endpoint, router

    def _setup_basic_routing(self, request, conv, tag):
        user_account = request.user_api.get_user_account()
        routing_table = request.user_api.get_routing_table(user_account)
        rt_helper = RoutingTableHelper(routing_table)

        conv_conn = str(
            GoConnector.for_conversation(conv.conversation_type, conv.key))
        tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
        rt_helper.add_entry(conv_conn, "default", tag_conn, "default")
        rt_helper.add_entry(tag_conn, "default", conv_conn, "default")
        user_account.save()

    def _setup_keyword_routing(self, request, conv, tag, router, endpoint):
        user_account = request.user_api.get_user_account()
        routing_table = request.user_api.get_routing_table(user_account)
        rt_helper = RoutingTableHelper(routing_table)

        conv_conn = str(
            GoConnector.for_conversation(conv.conversation_type, conv.key))
        tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
        rin_conn = str(
            GoConnector.for_router(
                router.router_type, router.key, GoConnector.INBOUND))
        rout_conn = str(
            GoConnector.for_router(
                router.router_type, router.key, GoConnector.OUTBOUND))
        rt_helper.add_entry(conv_conn, "default", rout_conn, endpoint)
        rt_helper.add_entry(rout_conn, endpoint, conv_conn, "default")
        rt_helper.add_entry(rin_conn, "default", tag_conn, "default")
        rt_helper.add_entry(tag_conn, "default", rin_conn, "default")

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
