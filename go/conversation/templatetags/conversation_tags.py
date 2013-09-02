from django import template
from django.core.urlresolvers import reverse

from go.conversation.forms import ReplyToMessageForm
from go.base.utils import get_conversation_view_definition


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
    delivery_class = user_api.delivery_class_for_msg(message)
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
