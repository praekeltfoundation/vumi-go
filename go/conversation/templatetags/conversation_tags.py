import re
from copy import copy

from django.conf import settings
from django import template
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
from django.template.defaultfilters import stringfilter

from go.conversation.utils import PagedMessageCache
from go.conversation.forms import ReplyToMessageForm
from go.base import message_store_client as ms_client
from go.base.utils import page_range_window, get_conversation_view_definition

from vumi.message import TransportUserMessage


register = template.Library()


@register.simple_tag
def conversation_screen(conv, view_name='show'):
    # FIXME: Unhack this when all apps have definition modules.
    try:
        view_def = get_conversation_view_definition(
            conv.conversation_type, conv)
    except AttributeError:
        return '/conversations/%s/' % (conv.key,)
    return view_def.get_view_url(view_name, conversation_key=conv.key)


@register.simple_tag
def conversation_action(conv, action_name):
    return reverse('conversations:conversation_action', kwargs={
        'conversation_key': conv.key, 'action_name': action_name})


@register.assignment_tag
def get_contact_for_message(user_api, message, direction='inbound'):
    # This is a temporary work around to deal with the hackiness that
    # lives in `contact_for_addr()`. It used to expect to be passed a
    # `conversation.delivery_class` and this emulates that.
    # It falls back to the raw `transport_type` so that errors in
    # retrieving a contact return something useful for debugging (i.e.
    # the `transport_type` that failed to be looked up).
    delivery_class = {
        TransportUserMessage.TT_SMS: 'sms',
        TransportUserMessage.TT_USSD: 'ussd',
        TransportUserMessage.TT_XMPP: 'gtalk',
        TransportUserMessage.TT_TWITTER: 'twitter',
    }.get(message['transport_type'],
          message['transport_type'])
    user = message.user() if direction == 'inbound' else message['to_addr']
    return user_api.contact_store.contact_for_addr(
        delivery_class, unicode(user), create=True)


@register.assignment_tag
def get_reply_form_for_message(message):
    form = ReplyToMessageForm(initial={
        'to_addr': message['from_addr'],
        'in_reply_to': message['message_id'],
        })
    form.fields['to_addr'].widget.attrs['readonly'] = True
    return form


@register.filter
@stringfilter
def scrub_tokens(value):
    site = Site.objects.get_current()
    pattern = r'://%s/t/(\w+)/?' % (re.escape(site.domain),)
    replacement = '://%s/t/******/' % (site.domain,)
    return re.sub(pattern, replacement, value)
