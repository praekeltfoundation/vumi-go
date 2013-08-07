from urllib import urlencode

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator

from go.wizard.forms import Wizard1CreateForm, Wizard1ExistingRouterForm
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

    def _render(self, request, wizard_form=None, conversation_form=None,
                channel_form=None, router_form=None):
        return self.render_to_response({
            'wizard_form': wizard_form or Wizard1CreateForm(),
            'conversation_form': (conversation_form or
                                  NewConversationForm(request.user_api)),
            'channel_form': (channel_form or NewChannelForm(request.user_api)),
            'router_form': (router_form or
                            Wizard1ExistingRouterForm(request.user_api)),
        })


    def get(self, request):
        return self._render(request)

    def post(self, request):
        # TODO: Reuse new conversation/channel view logic here.
        wiz_form = Wizard1CreateForm(request.POST)
        conv_form = NewConversationForm(request.user_api, request.POST)
        chan_form = NewChannelForm(request.user_api, request.POST)
        router_form = Wizard1ExistingRouterForm(request.user_api, request.POST)

        forms_to_validate = [wiz_form, conv_form]
        # We do this on the raw POST data so we can validate in one step.
        if request.POST.get('channel_kind') == 'new':
            forms_to_validate.append(chan_form)
        elif request.POST.get('channel_kind') == 'existing':
            forms_to_validate.append(router_form)

        if not all(form.is_valid() for form in forms_to_validate):
            # TODO: Better validation.
            logger.info("Validation failed: %s" % (
                [frm.errors for frm in forms_to_validate],))
            print "Validation failed: %s" % (
                [frm.errors for frm in forms_to_validate],)
            return self._render(request, wizard_form=wiz_form,
                                conversation_form=conv_form,
                                channel_form=chan_form,
                                router_form=router_form)

        # Create conversation
        view_def, conv = self._create_conversation(
            request, conv_form.cleaned_data)

        wiz_data = wiz_form.cleaned_data
        if wiz_data['channel_kind'] == 'new':
            self._handle_new_channel(
                request, chan_form.cleaned_data, wiz_data['keyword'], conv)
        else:
            self._handle_existing_channel(
                request, router_form.cleaned_data, conv)

        messages.info(request, 'Conversation created successfully.')
        if view_def.is_editable:
            return redirect(view_def.get_view_url(
                'edit', conversation_key=conv.key))
        else:
            return redirect(view_def.get_view_url(
                'show', conversation_key=conv.key))

    def _handle_new_channel(self, request, chan_data, keyword, conv):
        channel = tuple(chan_data['channel'].split(':'))
        if channel[1]:
            tag = request.user_api.acquire_specific_tag(channel)
        else:
            tag = request.user_api.acquire_tag(channel[0])

        # Set up routing
        if keyword:
            # Create router
            endpoint, router = self._create_keyword_router(
                request, keyword, ':'.join(tag))
            self._setup_keyword_routing(
                request, conv, tag, router, endpoint)
        else:
            self._setup_basic_routing(request, conv, tag)

    def _handle_existing_channel(self, request, router_data, conv):
        # TODO: Check that keyword is unused.
        router = request.user_api.get_router(router_data['existing_router'])
        keyword = router_data['new_keyword']
        endpoint = 'keyword_%s' % (keyword.lower(),)
        # TODO: Better way to manage this kind of thing.
        kem = router.config.setdefault('keyword_endpoint_mapping', {})
        kem[keyword] = endpoint
        if endpoint not in router.extra_outbound_endpoints:
            router.extra_outbound_endpoints.append(endpoint)
        router.save()

        self._setup_keyword_routing(request, conv, None, router, endpoint)

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

        if tag is not None:
            tag_conn = str(GoConnector.for_transport_tag(tag[0], tag[1]))
            rin_conn = str(
                GoConnector.for_router(
                    router.router_type, router.key, GoConnector.INBOUND))
            rt_helper.add_entry(rin_conn, "default", tag_conn, "default")
            rt_helper.add_entry(tag_conn, "default", rin_conn, "default")

        conv_conn = str(
            GoConnector.for_conversation(conv.conversation_type, conv.key))
        rout_conn = str(
            GoConnector.for_router(
                router.router_type, router.key, GoConnector.OUTBOUND))
        rt_helper.add_entry(conv_conn, "default", rout_conn, endpoint)
        rt_helper.add_entry(rout_conn, endpoint, conv_conn, "default")

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
