import re

from django.conf import settings
from django import template
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from go.conversation.utils import PagedMessageCache, MessageStoreClient
from go.base.utils import page_range_window


register = template.Library()


@register.inclusion_tag(
    'conversation/inclusion_tags/show_conversation_messages.html')
def show_conversation_messages(conversation, direction=None, page=None,
                                batch_id=None, query=None, token=None):
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

    context = {
        'batch_id': batch_id,
        'conversation': conversation,
        'inbound_message_paginator': inbound_message_paginator,
        'outbound_message_paginator': outbound_message_paginator,
        'inbound_uniques_count': conversation.count_inbound_uniques(),
        'outbound_uniques_count': conversation.count_outbound_uniques(),
        'message_direction': direction,
    }

    # If we're doing a query we can shortcut the results as we don't
    # need all the message paginator stuff since we're loading the results
    # asynchronously with JavaScript.
    msc = MessageStoreClient(settings.MESSAGE_STORE_API_URL)
    if query and not token:
        token = msc.match(batch_id, direction, [{
            'key': 'msg.content',
            'pattern': re.escape(query),
            'flags': 'i',
            }])
        context.update({
            'query': query,
            'token': token,
        })
        return context
    elif query and token:
        match_result = msc.get_match_results(batch_id, direction, token,
            page=int(page), page_size=20)
        message_paginator = match_result.paginator
        context.update({
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

    context.update({
        'message_page': message_page,
        'message_page_range': page_range_window(message_page, 5),
    })
    return context
