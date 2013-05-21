from StringIO import StringIO
from zipfile import ZipFile

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

    zipio = StringIO()
    zf = ZipFile(zipio, "a")
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
def send_one_off_reply(account_key, conversation_key, in_reply_to, content):
    user_api = VumiUserApi.from_config_sync(account_key,
                                            settings.VUMI_API_CONFIG)
    inbound_message = user_api.api.mdb.get_inbound_message(in_reply_to)
    if inbound_message is None:
        print 'Replying to an unknown message'

    conversation = user_api.get_wrapped_conversation(conversation_key)
    [tag] = conversation.get_tags()
    msg_options = conversation.make_message_options(tag)
    msg_options['in_reply_to'] = in_reply_to
    conversation.dispatch_command('send_message', command_data={
        "batch_id": conversation.get_latest_batch_key(),
        "conversation_key": conversation.key,
        "to_addr": inbound_message['from_addr'],
        "content": content,
        "msg_options": msg_options,
        })
