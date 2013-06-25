from django.contrib import messages
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse


class DjangoTokenManager(object):

    def __init__(self, token_manager):
        self.tm = token_manager

    def generate_token(self, user_token_size=6):
        return self.tm.generate_token(user_token_size)

    def generate(self, redirect_to, user_id=None, lifetime=None, token=None,
                    extra_params=None):
        return self.tm.generate(redirect_to, user_id=user_id,
                lifetime=lifetime, token=token, extra_params=extra_params)

    def get(self, token, verify=None):
        return self.tm.get(token, verify=verify)

    def verify_get(self, full_token):
        return self.tm.verify_get(full_token)

    def delete(self, token):
        return self.tm.delete(token)

    def generate_callback_token(self, return_to, message, callback,
            callback_args, callback_kwargs, message_level=None, user_id=None,
            lifetime=None):

        message_level = message_level or messages.INFO
        callback_name = '%s.%s' % (callback.__module__, callback.__name__)
        token = self.generate(reverse('token_task'), user_id=user_id,
            lifetime=lifetime, extra_params={
                'callback_name': callback_name,
                'callback_args': callback_args,
                'callback_kwargs': callback_kwargs,
                'return_to': return_to,
                'message': message,
                'message_level': message_level,
            })
        return token

    def parse_full_token(self, full_token):
        return self.tm.parse_full_token(full_token)

    def url_for_token(self, token):
        site = Site.objects.get_current()
        return 'http://%s%s' % (site.domain, reverse('token',
                    kwargs={'token': token}))
