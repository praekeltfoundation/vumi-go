from StringIO import StringIO

from celery.task import task

from django.conf import settings
from django.core.mail import EmailMessage

from go.vumitools.api import VumiUserApi
from go.base.models import UserProfile
from go.base.utils import UnicodeCSVWriter


@task(ignore_result=True)
def export_conversation_messages(account_key, conversation_key):
    """
    Export the messages in a conversation via email.

    :param str account_key:
        The account holder's account account_key
    :param str conversation_key:
        The key of the conversation we want to export the messages for.
    """

    # The field names to export
    field_names = [
        'from_addr',
        'to_addr',
        'timestamp',
        'content',
        'message_id',
        'in_reply_to',
    ]

    api = VumiUserApi.from_config_sync(account_key, settings.VUMI_API_CONFIG)
    user_profile = UserProfile.objects.get(user_account=account_key)
    conversation = api.get_wrapped_conversation(conversation_key)
    io = StringIO()

    writer = UnicodeCSVWriter(io)
    writer.writerow(field_names)

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

    for message in all_messages:
        writer.writerow([unicode(message.payload.get(fn) or '')
                            for fn in field_names])

    email = EmailMessage(
        'Conversation message export: %s' % (conversation.subject,),
        'Please find the messages of the conversation %s attached.\n' % (
            conversation.subject),
        settings.DEFAULT_FROM_EMAIL, [user_profile.user.email])
    email.attach('messages-export.csv', io.getvalue(), 'text/csv')
    email.send()
