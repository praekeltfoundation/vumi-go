from urllib import urlencode
import urlparse

from django.shortcuts import Http404, redirect
from django.contrib.auth.views import logout
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from vumi.utils import load_class_by_string

from go.base.utils import get_redis_manager
from go.vumitools.token_manager import TokenManager


def token(request, token):
    tm = TokenManager(get_redis_manager().sub_manager('token_manager'))
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


@login_required
def token_task(request):
    api = request.user_api.api

    token = request.GET.get('token')
    token_data = api.token_manager.verify_get(token)
    if not token_data:
        raise Http404

    params = token_data['extra_params']
    callback_name = params['callback_name']
    callback_args = params['callback_args']
    callback_kwargs = params['callback_kwargs']
    return_to = params['return_to']
    message = params['message']
    message_level = params['message_level']

    callback = load_class_by_string(callback_name)
    callback(*callback_args, **callback_kwargs)
    messages.add_message(request, message_level, message)
    return redirect(return_to)
