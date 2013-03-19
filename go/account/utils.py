from operator import attrgetter

from go.base.utils import vumi_api_for_user
from go.vumitools.conversation.models import (CONVERSATION_TYPES,
                                                CONVERSATION_RUNNING)

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


def get_uniques(contact_store, contact_keys=None,
                    plucker=attrgetter('msisdn')):
    uniques = set()
    contacts_manager = contact_store.contacts
    contact_keys = contact_keys or contact_store.list_contacts()
    for bunch in contacts_manager.load_all_bunches(contact_keys):
        uniques.update([plucker(contact) for contact in bunch])
    return uniques


def get_messages_count(conversations):
    totals = {}
    for conv in conversations:
        totals.setdefault(conv.conversation_type, {})
        totals[conv.conversation_type].setdefault('sent', 0)
        totals[conv.conversation_type].setdefault('received', 0)
        totals[conv.conversation_type]['sent'] += conv.count_sent_messages()
        totals[conv.conversation_type]['received'] += conv.count_replies()
    return totals


def send_user_account_summary(user):
    user_api = vumi_api_for_user(user)
    contact_store = user_api.contact_store
    conv_store = user_api.conversation_store

    contact_keys = contact_store.list_contacts()
    uniques = get_uniques(contact_store, contact_keys=contact_keys,
                            plucker=attrgetter('msisdn'))
    conversation_keys = conv_store.list_conversations()

    all_conversations = []
    bunches = conv_store.conversations.load_all_bunches(conversation_keys)
    for bunch in bunches:
        all_conversations.extend([user_api.wrap_conversation(conv)
                                    for conv in bunch])
    all_conversations.sort(key=(lambda conv: conv.created_at), reverse=True)

    active_conversations = {}
    known_types = dict(CONVERSATION_TYPES)
    for conv in all_conversations:
        conv_list = active_conversations.setdefault(
            known_types.get(conv.conversation_type, 'Unknown'), [])
        if conv.get_status() == CONVERSATION_RUNNING:
            conv_list.append(conv)

    message_count = get_messages_count(all_conversations)
    total_message_count = sum(conv_type['sent'] + conv_type['received']
                                for conv_type in message_count.values())

    send_mail('Vumi Go Account Summary',
        render_to_string('account/account_summary_mail.txt', {
            'all_conversations': all_conversations,
            'user': user,
            'unique_identifier': 'contact number',
            'total_uniques': len(uniques),
            'total_contacts': len(contact_keys),
            'total_message_count': total_message_count,
            'active_conversations': active_conversations,
            }), settings.DEFAULT_FROM_EMAIL, [user.email],
        fail_silently=False)
