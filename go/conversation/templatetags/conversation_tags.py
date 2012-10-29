from django import template
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from go.conversation.utils import PagedMessageCache
from go.base.utils import page_range_window


register = template.Library()


@register.inclusion_tag(
    'conversation/inclusion_tags/show_conversation_messages.html')
def show_conversation_messages(conversation, direction=None, page=None,
                                batch_id=None):
    direction = direction or 'inbound'
    # Paginator starts counting at 1 so would also be invalid
    page = page or 1
    inbound_message_paginator = Paginator(
        PagedMessageCache(conversation.count_replies(),
            lambda start, stop: conversation.replies(start, stop, batch_id)),
            20)
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
        'inbound_message_paginator': inbound_message_paginator,
        'outbound_message_paginator': outbound_message_paginator,
        'inbound_uniques_count': conversation.count_inbound_uniques(),
        'outbound_uniques_count': conversation.count_outbound_uniques(),
        'message_direction': direction,
        'message_page': message_page,
        'message_page_range': page_range_window(message_page, 5),
    }
