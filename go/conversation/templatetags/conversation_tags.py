import re
from copy import copy

from django.conf import settings
from django import template
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.sites.models import Site
from django.template.defaultfilters import stringfilter

from go.conversation.utils import PagedMessageCache
from go.base import message_store_client as ms_client
from go.base.utils import page_range_window

from vumi.message import TransportUserMessage


register = template.Library()


@register.inclusion_tag(
    'conversation/inclusion_tags/show_conversation_messages.html',
    takes_context=True)
def show_conversation_messages(context, conversation, direction=None,
                                page=None, batch_id=None, query=None,
                                token=None):
    """
    Render the messages sent & received for this conversation.

    :param ConversationWrapper conversation:
        The conversation to show messages for.
    :param str direction:
        Either 'inbound' or 'outbound', defaults to 'inbound'
    :param int page:
        The page to display for the pagination.
    :param str batch_id:
        The batch_id to show messages for.
    :param str query:
        The query string to search messages for in the batch's inbound
        messages.
    """

    batch_id = batch_id or conversation.get_latest_batch_key()
    direction = 'outbound' if direction == 'outbound' else 'inbound'

    # Paginator starts counting at 1 so 0 would also be invalid
    page = page or 1
    inbound_message_paginator = Paginator(
        PagedMessageCache(conversation.count_replies(),
            lambda start, stop: conversation.received_messages(
                start, stop, batch_id)), 20)
    outbound_message_paginator = Paginator(
        PagedMessageCache(conversation.count_sent_messages(),
            lambda start, stop: conversation.sent_messages(start, stop,
                batch_id)), 20)

    # We have to copy the original context here so we have full access
    # to all variables that were originally made available in the Template
    # with RequestContext and friends. If we do not do this then the `user_api`
    # is not available for the tags inside this inclusion tag.
    tag_context = copy(context)
    tag_context.update({
        'batch_id': batch_id,
        'conversation': conversation,
        'inbound_message_paginator': inbound_message_paginator,
        'outbound_message_paginator': outbound_message_paginator,
        'inbound_uniques_count': conversation.count_inbound_uniques(),
        'outbound_uniques_count': conversation.count_outbound_uniques(),
        'message_direction': direction,
    })

    # If we're doing a query we can shortcut the results as we don't
    # need all the message paginator stuff since we're loading the results
    # asynchronously with JavaScript.
    client = ms_client.Client(settings.MESSAGE_STORE_API_URL)
    if query and not token:
        token = client.match(batch_id, direction, [{
            'key': 'msg.content',
            'pattern': re.escape(query),
            'flags': 'i',
            }])
        tag_context.update({
            'query': query,
            'token': token,
        })
        return tag_context
    elif query and token:
        match_result = ms_client.MatchResult(client, batch_id, direction,
                                                token, page=int(page),
                                                page_size=20)
        message_paginator = match_result.paginator
        tag_context.update({
            'token': token,
            'query': query,
            })

    elif direction == 'inbound':
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
    return tag_context


@register.assignment_tag
def get_contact_for_message(user_api, message):
    # This is a temporary work around to deal with the hackiness that
    # lives in `contact_for_addr()`. It used to expect to be passed a
    # `conversation.delivery_class` and this emulates that.
    delivery_class = {
        TransportUserMessage.TT_SMS: 'sms',
        TransportUserMessage.TT_USSD: 'ussd',
        TransportUserMessage.TT_XMPP: 'gtalk',
        TransportUserMessage.TT_TWITTER: 'twitter',
    }.get(message['transport_type'], 'unkown')
    return user_api.contact_store.contact_for_addr(
        delivery_class, unicode(message.user()))


@register.filter
@stringfilter
def scrub_tokens(value):
    site = Site.objects.get_current()
    pattern = r'://%s/t/(\w+)/?' % (re.escape(site.domain),)
    replacement = '://%s/t/******/' % (site.domain,)
    return re.sub(pattern, replacement, value)
