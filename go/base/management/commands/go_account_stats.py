from vumi.message import parse_vumi_date

from go.base.command_utils import BaseGoCommand


def print_dates(bucket, io):
    items = sorted(bucket.items(), key=lambda t: t[0])
    for item, count in items:
        io.write('%s: %s\n' % (item.strftime('%Y-%m-%d'), count))


class Command(BaseGoCommand):
    help = """
    Generate stats for a given Vumi Go account.

    """
    args = "<email-address> <command>"
    encoding = 'utf-8'

    def handle_no_command(self, *args, **options):

        if len(args) == 0:
            self.print_command_summary()
            return
        elif len(args) < 2:
            self.err(u'Usage <email-address> <command>\n')
            return

        email_address = args[0]
        command = args[1]

        user, api = self.mk_user_api(email_address)

        handler = getattr(self, 'handle_%s' % (command,), self.unknown_command)
        handler(user, api, args[2:])

    def out(self, data):
        self.stdout.write(data.encode(self.encoding))

    def err(self, data):
        self.stderr.write(data.encode(self.encoding))

    def print_command_summary(self):
        self.out(u'Known commands:\n')
        handlers = [func for func in dir(self) if func.startswith('handle_')]
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
        conversations = sorted(
            map(api.get_wrapped_conversation,
                api.conversation_store.list_conversations()),
            key=lambda c: c.created_at)
        if 'active' in options:
            conversations = [c for c in conversations if c.active()]
        for index, conversation in enumerate(conversations):
            self.out(u'%s. %s (%s) [%s]\n' % (
                index, conversation.name, conversation.created_at,
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
        qms = api.api.get_query_message_store()
        self.out(u'Conversation: %s\n' % (conversation.name,))

        batch_key = conversation.batch.key
        self.do_batch_key(qms, batch_key)
        self.do_batch_key_breakdown(qms, batch_key)

    def _count_results(self, index_page):
        count = 0
        while index_page is not None:
            count += len(index_page)
            index_page = index_page.next_page()
        return count

    def do_batch_key(self, qms, batch_key):
        in_count = self._count_results(
            qms.list_batch_inbound_messages(batch_key))
        out_count = self._count_results(
            qms.list_batch_outbound_messages(batch_key))
        self.out(u'Total Received in batch %s: %s\n' % (batch_key, in_count))
        self.out(u'Total Sent in batch %s: %s\n' % (batch_key, out_count))

    def parse_timestamp_to_date(self, timestamp):
        return parse_vumi_date(timestamp).date()

    def collect_stats(self, index_page):
        per_date = {}
        uniques = set()
        while index_page is not None:
            for _message_id, timestamp, addr in index_page:
                date = self.parse_timestamp_to_date(timestamp)
                per_date.setdefault(date, 0)
                per_date[date] += 1
                uniques.add(addr)
            index_page = index_page.next_page()
        return per_date, uniques

    def do_batch_key_breakdown(self, qms, batch_key):
        inbound = qms.list_batch_inbound_messages(batch_key)
        inbound_per_date, inbound_uniques = self.collect_stats(inbound)
        outbound = qms.list_batch_outbound_messages(batch_key)
        outbound_per_date, outbound_uniques = self.collect_stats(outbound)
        all_uniques = inbound_uniques.union(outbound_uniques)

        self.out(u'Total Uniques: %s\n' % (len(all_uniques),))
        self.out(u'Received per date:\n')
        print_dates(inbound_per_date, self.stdout)
        self.out(u'Sent per date:\n')
        print_dates(outbound_per_date, self.stdout)
