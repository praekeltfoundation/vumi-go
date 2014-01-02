import warnings

from StringIO import StringIO
from zipfile import ZipFile, ZIP_DEFLATED

from celery.task import task

from django.conf import settings
from django.core.mail import EmailMessage

from go.vumitools.api import VumiUserApi
from go.base.models import UserProfile
from go.base.utils import UnicodeCSVWriter, grouper


# The field names to export
conversation_export_field_names = [
    'timestamp',
    'from_addr',
    'to_addr',
    'content',
    'message_id',
    'in_reply_to',
]


def write_messages(writer, messages):
    for message in messages:
        writer.writerow([unicode(message.payload.get(fn) or '')
                         for fn in conversation_export_field_names])
    return messages


def email_export(user_profile, conversation, io):
    zipio = StringIO()
    zf = ZipFile(zipio, "a", ZIP_DEFLATED)
    zf.writestr("messages-export.csv", io.getvalue())
    zf.close()

    email = EmailMessage(
        'Conversation message export: %s' % (conversation.name,),
        'Please find the messages of the conversation %s attached.\n' % (
            conversation.name),
        settings.DEFAULT_FROM_EMAIL, [user_profile.user.email])
    email.attach('messages-export.zip', zipio.getvalue(), 'application/zip')
    email.send()


@task(ignore_result=True)
def export_conversation_messages_unsorted(account_key, conversation_key):
    """
    Export the messages from a conversation as they come from the message
    store. Completely unsorted.

    :param str account_key:
        The account holder's account account_key
    :param str conversation_key:
        The key of the conversation we want to export the messages for.
    """
    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    user_profile = UserProfile.objects.get(user_account=account_key)
    conversation = api.get_wrapped_conversation(conversation_key)
    mdb = conversation.mdb
    io = StringIO()

    writer = UnicodeCSVWriter(io)
    writer.writerow(conversation_export_field_names)

    inbound_keys = conversation.inbound_keys()
    outbound_keys = conversation.outbound_keys()

    for keys_chunk in grouper(inbound_keys, 20):
        messages = conversation.collect_messages(
            message_keys, conversation.messages.inbound_messages,
            include_sensitive=False, scrubber=None)
        write_messages(writer, messages)

    for keys_chunk in grouper(outbound_keys, 20):
        messages = conversation.collect_messages(
            message_keys, conversation.messages.outbound_messages,
            include_sensitive=False, scrubber=None)
        write_messages(writer, messages)

    email_export(user_profile, conversation, io)


@task(ignore_result=True)
def export_conversation_messages(account_key, conversation_key):
    warnings.warn('export_conversation_messages() is deprecated. '
                  'Please use export_conversation_messages_sorted() instead',
                  category=DeprecationWarning)
    return export_conversation_messages_sorted(account_key, conversation_key)


@task(ignore_result=True)
def export_conversation_messages_sorted(account_key, conversation_key):
    """
    Export the messages (threaded and sorted) in a conversation via email.

    NOTE: This loads _all_ messages from the conversation into memory.

    :param str account_key:
        The account holder's account account_key
    :param str conversation_key:
        The key of the conversation we want to export the messages for.
    """

    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    user_profile = UserProfile.objects.get(user_account=account_key)
    conversation = api.get_wrapped_conversation(conversation_key)
    io = StringIO()

    writer = UnicodeCSVWriter(io)
    writer.writerow(conversation_export_field_names)

    # limiting to 0 results in getting the full set, creating lists of tuples
    # with direction sort we can sort sent & received messages in a somewhat
    # threaded fashion further down.
    sent_messages = [('sent', msg)
                     for msg in conversation.sent_messages(limit=0)]
    received_messages = [('received', msg)
                         for msg in conversation.received_messages(limit=0)]

    def sort_by_addr_and_timestap(entry):
        """
        Apply sorting based on direction of the message.
        The to_addr & from_addr switch depending on whether the message
        was sent or received. We always need to sort on the addr of the end
        user which means switching based on direction.
        """
        direction, message = entry
        if direction == 'sent':
            return (message['to_addr'], message['timestamp'])
        return (message['from_addr'], message['timestamp'])

    all_messages = [msg for directon, msg in
                    sorted(sent_messages + received_messages,
                           key=sort_by_addr_and_timestap)]

    write_messages(writer, all_messages)
    email_export(user_profile, conversation, io)
