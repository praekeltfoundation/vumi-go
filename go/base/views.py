import urllib
import urlparse

from django.conf import settings
from django.shortcuts import render, Http404, redirect
from django.contrib.auth.views import logout
from django.contrib import messages
from django.core.urlresolvers import reverse

from vumi.persist.redis_manager import RedisManager
from vumi.utils import load_class_by_string

from go.base.token_manager import TokenManager


def todo(request):  # pragma: no cover
    return render(request, 'base/todo.html', {
    })


def token(request, token):
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
        return redirect('%s?%s' % (path, urllib.urlencode(params)))

    # If we got here then we need authentication and the user's either not
    # logged in or is logged in with a wrong account.
    if request.user.is_authenticated():
        logout(request)
        messages.info(request, 'Wrong account for this token.')
    return redirect('%s?%s' % (reverse('auth_login'), urllib.urlencode({
        'next': reverse('token', kwargs={'token': token}),
        })))


def token_task(request):
    redis = RedisManager.from_config(settings.VUMI_API_CONFIG['redis_manager'])
    tm = TokenManager(redis.sub_manager('token_manager'))

    token = request.GET.get('token')
    token_data = tm.verify_get(token)
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
