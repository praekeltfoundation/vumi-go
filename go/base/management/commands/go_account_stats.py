from django.core.management.base import BaseCommand

from go.base.utils import vumi_api_for_user
from go.base.command_utils import get_user_by_email


def per_date(collection):
    bucket = {}
    for message in collection:
        key = message.msg['timestamp'].date()
        bucket.setdefault(key, 0)
        bucket[key] += 1
    return bucket


def print_dates(bucket, io):
    items = sorted(bucket.items(), key=lambda t: t[0])
    for item, count in items:
        io.write('%s: %s\n' % (item.strftime('%Y-%m-%d'), count))


def get_inbound(message_store, keys):
    for key in keys:
        yield message_store.inbound_messages.load(key)


def get_outbound(message_store, keys):
    for key in keys:
        yield message_store.outbound_messages.load(key)


def get_msisdns(key, collection):
    uniques = set([])
    for message in collection:
        uniques.add(message.msg[key])
    return uniques


class Command(BaseCommand):
    help = """
    Generate stats for a given Vumi Go account.

    """
    args = "<email-address> <command>"
    encoding = 'utf-8'

    def handle(self, *args, **options):

        if len(args) == 0:
            self.print_command_summary()
            return
        elif len(args) < 2:
            self.err(u'Usage <email-address> <command>\n')
            return

        email_address = args[0]
        command = args[1]

        user = get_user_by_email(email=email_address)
        api = self.get_api(user)

        handler = getattr(self, 'handle_%s' % (command,),
            self.unknown_command)
        handler(user, api, args[2:])

    def get_api(self, user):
        return vumi_api_for_user(user)

    def out(self, data):
        self.stdout.write(data.encode(self.encoding))

    def err(self, data):
        self.stderr.write(data.encode(self.encoding))

    def print_command_summary(self):
        self.out(u'Known commands:\n')
        handlers = [func for func in dir(self)
                        if func.startswith('handle_')]
        for handler in sorted(handlers):
            command = handler.split('_', 1)[1]
            func = getattr(self, handler)
            self.out(u'%s:' % (command,))
            self.out(u'%s\n' % (func.__doc__,))
        return

    def unknown_command(self, *args, **kwargs):
        self.err(u'Unknown command\n')

    def handle_list_conversations(self, user, api, options):
        """
        List all conversations for the user.

            go_account_stats <email-address> list_conversations
            go_account_stats <email-address> list_conversations active

        Appending 'active' limits the list to only active conversations.
        """
        conversations = sorted(map(api.get_wrapped_conversation,
                            api.conversation_store.list_conversations()),
                            key=lambda c: c.created_at)
        if 'active' in options:
            conversations = [c for c in conversations if not c.ended()]
        for index, conversation in enumerate(conversations):
            self.out(u'%s. %s (%s) [%s]\n' % (index,
                conversation.name, conversation.created_at,
                conversation.key))

    def handle_stats(self, user, api, options):
        """
        Get stats for a given conversation key.

            go_account_stats <email-address> stats <conversation-key>

        """
        if not len(options) == 1:
            self.err(u'Provide a conversation key')
            return
        conv_key = options[0]
        conversation = api.get_wrapped_conversation(conv_key)
        message_store = api.api.mdb
        self.out(u'Conversation: %s\n' % (conversation.name,))

        batch_key = conversation.batch.key
        self.do_batch_key(message_store, batch_key)
        self.do_batch_key_breakdown(message_store, batch_key)

    def do_batch_key(self, message_store, batch_key):
        self.out(u'Total Received in batch %s: %s\n' % (
            batch_key, message_store.batch_inbound_count(batch_key),))
        self.out(u'Total Sent in batch %s: %s\n' % (
            batch_key, message_store.batch_outbound_count(batch_key),))

    def do_batch_key_breakdown(self, message_store, batch_key):
        inbound_keys = message_store.batch_inbound_keys(batch_key)
        outbound_keys = message_store.batch_outbound_keys(batch_key)

        inbound = list(get_inbound(message_store, inbound_keys))
        outbound = list(get_outbound(message_store, outbound_keys))
        inbound_msisdns = get_msisdns('from_addr', inbound)
        outbound_msisdns = get_msisdns('to_addr', outbound)
        all_msisdns = inbound_msisdns.union(outbound_msisdns)

        self.out(u'Total Uniques: %s\n' % (len(all_msisdns),))
        self.out(u'Received per date:\n')
        print_dates(per_date(inbound), self.stdout)
        self.out(u'Sent per date:\n')
        print_dates(per_date(outbound), self.stdout)
