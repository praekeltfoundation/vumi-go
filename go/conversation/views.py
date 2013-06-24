import urlparse
from urllib import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, Http404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth.views import logout
from django.core.urlresolvers import reverse

from vumi.persist.redis_manager import RedisManager

from go.conversation.forms import ConversationSearchForm
from go.base.utils import get_conversation_view_definition, conversation_or_404
from go.conversation_tmp.forms import CampaignGeneralForm
from go.vumitools.token_manager import TokenManager


CONVERSATIONS_PER_PAGE = 12


@login_required
def index(request):
    # grab the fields from the GET request
    user_api = request.user_api
    conversation_types = [(app['namespace'], app['display_name'])
                          for app in user_api.applications().values()]
    search_form = ConversationSearchForm(
        request.GET, conversation_types=conversation_types)
    search_form.is_valid()

    conversation_status = search_form.cleaned_data['conversation_status']
    conversation_type = search_form.cleaned_data['conversation_type']
    query = search_form.cleaned_data['query']

    get_conversations = {
        'running': user_api.running_conversations,
        'finished': user_api.finished_conversations,
        'draft': user_api.draft_conversations,
    }.get(conversation_status, user_api.active_conversations)

    conversations = [user_api.wrap_conversation(c)
                        for c in get_conversations()]

    if conversation_type:
        conversations = [c for c in conversations
                         if c.conversation_type == conversation_type]

    if query:
        conversations = [c for c in conversations
                         if query.lower() in c.name.lower()]

    # sort with newest first
    conversations = sorted(conversations, key=lambda c: c.created_at,
                            reverse=True)

    paginator = Paginator(conversations, CONVERSATIONS_PER_PAGE)
    try:
        page = paginator.page(request.GET.get('p', 1))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    pagination_params = urlencode({
        'query': query,
        'conversation_status': conversation_status,
        'conversation_type': conversation_type,
        })

    return render(request, 'conversation/dashboard.html', {
        'conversations': conversations,
        'paginator': paginator,
        'pagination_params': pagination_params,
        'page': page,
        'query': query,
        'search_form': search_form,
    })


@login_required
def conversation(request, conversation_key, path_suffix):
    conv = conversation_or_404(request.user_api, conversation_key)
    view_def = get_conversation_view_definition(
        conv.conversation_type, conv)
    view = view_def.get_view(path_suffix)
    return view(request, conv)


@login_required
def conversation_action(request, conversation_key, action_name):
    conv = conversation_or_404(request.user_api, conversation_key)
    view_def = get_conversation_view_definition(
        conv.conversation_type, conv)
    view = view_def.get_action_view(action_name)
    return view(request, conv)


@login_required
@require_POST
def new_conversation(request):
    # TODO: description?
    form = CampaignGeneralForm(request.POST)
    if not form.is_valid():
        # TODO: Something more sensible here?
        return HttpResponse(
            "Invalid form: %s" % (form.errors,), status=400)
    conversation_type = form.cleaned_data['type']
    conv = request.user_api.new_conversation(
        conversation_type, name=form.cleaned_data['name'],
        description=u'', config={})
    messages.info(request, 'Conversation created successfully.')

    view_def = get_conversation_view_definition(
        conv.conversation_type, conv)

    # TODO: Better workflow here?

    next_view = 'show'
    action = request.POST.get('action')
    if action == 'draft':
        # save and go back to list.
        return redirect('conversations:index')
    elif view_def.edit_conversation_forms is not None:
        next_view = 'edit'

    return redirect(view_def.get_view_url(
        next_view, conversation_key=conv.key))


def token(request, token):
    # This is special, since we don't necessarily have an authenticated user
    # and we definitely don't have a conversation.
    redis = RedisManager.from_config(settings.VUMI_API_CONFIG['redis_manager'])
    tm = TokenManager(redis.sub_manager('token_manager'))
    token_data = tm.get(token)
    if not token_data:
        raise Http404

    user_id = int(token_data['user_id'])
    redirect_to = token_data['redirect_to']
    system_token = token_data['system_token']

    # If we're authorized and we're the same user_id then redirect to
    # where we need to be
    if not user_id or request.user.id == user_id:
        path, _, qs = redirect_to.partition('?')
        params = urlparse.parse_qs(qs)
        # since the token can be custom we prepend the size of the user_token
        # to the token being forwarded so the view handling the `redirect_to`
        # can lookup the token and verify the system token.
        params.update({'token': '%s-%s%s' % (len(token), token, system_token)})
        return redirect('%s?%s' % (path, urlencode(params)))

    # If we got here then we need authentication and the user's either not
    # logged in or is logged in with a wrong account.
    if request.user.is_authenticated():
        logout(request)
        messages.info(request, 'Wrong account for this token.')
    return redirect('%s?%s' % (reverse('auth_login'), urlencode({
        'next': reverse('token', kwargs={'token': token}),
        })))
