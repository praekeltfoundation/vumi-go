from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from go.base.utils import vumi_api_for_user


def per_date(collection):
    bucket = {}
    for message in collection:
        key = message['timestamp'].date()
        bucket.setdefault(key, 0)
        bucket[key] += 1
    return bucket


def print_dates(bucket, io):
    items = sorted(bucket.items(), key=lambda t: t[0])
    for item, count in items:
        io.write('%s: %s\n' % (item.strftime('%Y-%m-%d'), count))


def get_inbound(conversation):
    batch_keys = conversation.get_batch_keys()
    replies = []
    for batch_id in batch_keys:
        replies.extend(conversation.mdb.batch_replies(batch_id))
    return replies


def get_outbound(conversation):
    batch_keys = conversation.get_batch_keys()
    messages = []
    for batch_id in batch_keys:
        messages.extend(conversation.mdb.batch_messages(batch_id))
    return messages


def get_msisdns(key, collection):
    uniques = set([])
    for message in collection:
        uniques.add(message[key])
    return uniques


class Command(BaseCommand):
    help = """
    Generate stats for a given Vumi Go account.

    """
    args = "<email-address> <command>"

    def handle(self, *args, **options):

        if len(args) == 0:
            self.print_command_summary()
            return
        elif len(args) < 2:
            self.stderr.write('Usage <email-address> <command>\n')
            return

        email_address = args[0]
        command = args[1]

        try:
            user = User.objects.get(username=email_address)
            api = self.get_api(user)
        except User.DoesNotExist:
            self.stderr.write('Account does not exist\n')

        handler = getattr(self, 'handle_%s' % (command,), self.unknown_command)
        handler(user, api, args[2:])

    def get_api(self, user):
        return vumi_api_for_user(user)

    def print_command_summary(self):
        self.stdout.write('Known commands:\n')
        handlers = [func for func in dir(self)
                        if func.startswith('handle_')]
        for handler in sorted(handlers):
            command = handler.split('_', 1)[1]
            func = getattr(self, handler)
            self.stdout.write('%s:' % (command,))
            self.stdout.write('%s\n' % (func.__doc__,))
        return

    def unknown_command(self, *args, **kwargs):
        self.stderr.write('Unknown command\n')

    def handle_list_conversations(self, user, api, options):
        """
        List all conversations for the user.

            go_account_stats <email-address> list_conversations
            go_account_stats <email-address> list_conversations active

        Appending 'active' limits the list to only active conversations.
        """
        conversations = sorted(map(api.wrap_conversation,
                            api.conversation_store.list_conversations()),
                            key=lambda c: c.created_at)
        if 'active' in options:
            conversations = [c for c in conversations if not c.ended()]
        for index, conversation in enumerate(conversations):
            self.stdout.write('%s. %s (%s) [%s]\n' % (index,
                conversation.subject, conversation.created_at,
                conversation.key))

    def handle_stats(self, user, api, options):
        """
        Get stats for a given conversation key.

            go_account_stats <email-address> stats <conversation-key>

        """
        if not len(options) == 1:
            self.stderr.write('Provide a conversation key')
            return
        conv_key = options[0]
        raw_conv = api.conversation_store.get_conversation_by_key(conv_key)
        conversation = api.wrap_conversation(raw_conv)

        self.stdout.write('Conversation: %s\n' % (conversation.subject,))

        inbound = get_inbound(conversation)
        outbound = get_outbound(conversation)
        inbound_msisdns = get_msisdns('from_addr', inbound)
        outbound_msisdns = get_msisdns('to_addr', outbound)
        all_msisdns = inbound_msisdns.union(outbound_msisdns)

        self.stdout.write('Total Received: %s\n' % (len(inbound),))
        self.stdout.write('Total Sent: %s\n' % (len(outbound),))
        self.stdout.write('Total Uniques: %s\n' % (len(all_msisdns),))
        self.stdout.write('Received per date:\n')
        print_dates(per_date(inbound), self.stdout)
        self.stdout.write('Sent per date:\n')
        print_dates(per_date(outbound), self.stdout)
