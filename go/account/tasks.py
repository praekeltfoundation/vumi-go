from operator import attrgetter

from celery.task import task

from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from go.base.utils import vumi_api_for_user
from go.account.utils import get_uniques, get_messages_count
from go.vumitools.conversation.models import (CONVERSATION_TYPES,
                                                CONVERSATION_RUNNING)


@task(ignore_result=True)
def update_account_details(user_id, first_name=None, last_name=None,
    new_password=None, email_address=None, msisdn=None,
    confirm_start_conversation=None, email_summary=None):
    user = User.objects.get(pk=user_id)
    profile = user.get_profile()
    account = profile.get_user_account()

    if new_password:
        user.set_password(new_password)
    user.first_name = first_name
    user.last_name = last_name
    user.email = email_address
    user.save()

    account.msisdn = unicode(msisdn)
    account.confirm_start_conversation = confirm_start_conversation
    account.email_summary = email_summary
    account.save()


@task(ignore_result=True)
def send_account_summary(user_id):
    user = User.objects.get(pk=user_id)
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
    all_conversations.sort(lambda conv: conv.created_at, reverse=True)

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
