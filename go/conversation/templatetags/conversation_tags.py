from django import template
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from go.conversation.utils import PagedMessageCache
from go.base.utils import page_range_window


register = template.Library()


@register.inclusion_tag(
    'conversation/inclusion_tags/show_conversation_messages.html')
def show_conversation_messages(conversation, direction=None, page=None,
                                batch_id=None, query=None):
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

    direction = direction or 'inbound'

    if query:
        return show_conversation_message_search(conversation, direction,
            batch_id, query)

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

    if direction == 'inbound':
        message_paginator = inbound_message_paginator
    else:
        message_paginator = outbound_message_paginator

    try:
        message_page = message_paginator.page(page)
    except PageNotAnInteger:
        message_page = message_paginator.page(1)
    except EmptyPage:
        message_page = message_paginator.page(message_paginator.num_pages)

    return {
        'query': query,
        'conversation': conversation,
        'inbound_message_paginator': inbound_message_paginator,
        'outbound_message_paginator': outbound_message_paginator,
        'inbound_uniques_count': conversation.count_inbound_uniques(),
        'outbound_uniques_count': conversation.count_outbound_uniques(),
        'message_direction': direction,
        'message_page': message_page,
        'message_page_range': page_range_window(message_page, 5),
    }


def show_conversation_message_search(conversation, direction, batch_id, query):
    """
    Use Riak search to find messages with content matching the given query.

    :param ConversationWrapper conversation:
        The conversation who's inbound messages are to be searched.
    :param str batch_id:
        The batch_id used to find messages with for this conversation.
    :param str query:
        The search term.
    """
    matching_messages = conversation.match_inbound_messages(query)
    print matching_messages
    return {
        'query': query,
        'conversation': conversation,
    }
