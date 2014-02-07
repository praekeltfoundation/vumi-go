from StringIO import StringIO
from zipfile import ZipFile, ZIP_DEFLATED

from celery.task import task

from django.conf import settings
from django.core.mail import EmailMessage

from go.vumitools.api import VumiUserApi
from go.base.models import UserProfile
from go.base.utils import UnicodeCSVWriter


# The field names to export
conversation_export_field_names = [
    'timestamp',
    'from_addr',
    'to_addr',
    'content',
    'message_id',
    'in_reply_to',
    'session_event',
    'transport_type',
    'direction',
]


def write_messages(writer, messages, extra=None):
    extra = extra or {}
    for message in messages:
        message_payload = message.payload
        message_payload.update(extra)
        writer.writerow([unicode(message_payload.get(fn) or '')
                         for fn in conversation_export_field_names])
    return messages


def load_messages_in_chunks(conversation, direction='inbound',
                            include_sensitive=False, scrubber=None):
    """
    Load the conversation's messages in chunks of `size`.
    Uses `proxy.load_all_bunches()` lower down but allows skipping and/or
    scrubbing of messages depending on `include_sensitive` and `scrubber`.

    :param Conversation conv:
        The conversation.
    :param str direction:
        The direction, either ``'inbound'`` or ``'outbound'``.
    :param bool include_sensitive:
        If ``False`` then all messages marked as `sensitive` are skipped.
        Defaults to ``False``.
    :param callable scrubber:
        If provided, this is called for every message allowing it to be
        modified on the fly.
    """
    if direction == 'inbound':
        bunches = conversation.mdb.inbound_messages.load_all_bunches(
            conversation.inbound_keys())
    elif direction == 'outbound':
        bunches = conversation.mdb.outbound_messages.load_all_bunches(
            conversation.outbound_keys())
    else:
        raise ValueError('Invalid value (%s) received for `direction`. '
                         'Only `inbound` and `outbound` are allowed.' %
                         (direction,))

    for messages in bunches:
        yield conversation.filter_and_scrub_messages(
            messages, include_sensitive=include_sensitive, scrubber=scrubber)


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

    io = StringIO()
    writer = UnicodeCSVWriter(io)
    writer.writerow(conversation_export_field_names)

    for messages in load_messages_in_chunks(conversation, 'inbound'):
        write_messages(writer, messages, extra={
            'direction': 'inbound',
        })

    for messages in load_messages_in_chunks(conversation, 'outbound'):
        write_messages(writer, messages, extra={
            'direction': 'outbound',
        })

    email_export(user_profile, conversation, io)
