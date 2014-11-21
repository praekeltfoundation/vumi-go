""" Retrieve stats on the Vumi Go system. """

from collections import defaultdict
from csv import DictWriter

from go.base.utils import vumi_api_for_user
from go.base.command_utils import BaseGoCommand, get_users, make_command_option


class Command(BaseGoCommand):
    help = """Generate stats for a Vumi Go system."""

    option_list = BaseGoCommand.option_list + (
        make_command_option(
            'conversation_types',
            help=(
                "A count of total, active and running conversations by"
                " conversation type.")),
        make_command_option(
            'conversation_types_by_month',
            help=(
                "A list of when conversations were started by type and"
                " date.")),
        make_command_option(
            'message_counts_by_month',
            help=(
                "Inbound and outbound message counts and total unique users"
                " by date and conversation type.")),
    )

    def handle_command_conversation_types(self, *args, **options):
        conv_types = set()
        conv_statuses = set()
        conv_archive_statuses = set()
        type_stats = {}

        for user in get_users():
            api = vumi_api_for_user(user)
            for key in api.conversation_store.list_conversations():
                conv = api.get_wrapped_conversation(key)
                conv_types.add(conv.conversation_type)
                stats = type_stats.setdefault(
                    conv.conversation_type, defaultdict(int))
                stats["total"] += 1

                conv_archive_statuses.add(conv.archive_status)
                stats[conv.archive_status] += 1

                if conv.active():
                    conv_statuses.add(conv.status)
                    stats[conv.status] += 1

        fields = (["type", "total"] + sorted(conv_statuses) +
                  sorted(conv_archive_statuses))
        writer = DictWriter(self.stdout, fields)
        writer.writerow(dict(zip(fields, fields)))
        for conv_type in sorted(conv_types):
            row = dict((f, 0) for f in fields)
            row["type"] = conv_type
            row.update(type_stats[conv_type])
            writer.writerow(row)

    def handle_command_conversation_types_by_month(self, *args, **options):
        conv_types = set()
        date_stats = {}

        for user in get_users():
            api = vumi_api_for_user(user)
            for key in api.conversation_store.list_conversations():
                conv = api.get_wrapped_conversation(key)
                conv_types.add(conv.conversation_type)
                day = conv.created_at.date().replace(day=1)
                day_stats = date_stats.setdefault(day, defaultdict(int))
                day_stats[conv.conversation_type] += 1

        fields = (["date"] + sorted(conv_types))
        writer = DictWriter(self.stdout, fields)
        writer.writerow(dict(zip(fields, fields)))
        for day in sorted(date_stats.iterkeys()):
            row = dict((f, 0) for f in fields)
            row["date"] = day.strftime("%m/%d/%Y")
            row.update(date_stats[day])
            writer.writerow(row)

    def _increment_msg_stats(self, conv, stats):
        batch_key = conv.batch.key
        mdb = conv.mdb
        cache = mdb.cache
        stats["conversations_started"] += 1
        stats["inbound_message_count"] += mdb.batch_inbound_count(batch_key)
        stats["outbound_message_count"] += mdb.batch_outbound_count(batch_key)
        stats["inbound_uniques"] += cache.count_from_addrs(batch_key)
        stats["outbound_uniques"] += cache.count_to_addrs(batch_key)

    def handle_command_message_counts_by_month(self, *args, **options):
        date_stats = {}

        for user in get_users():
            api = vumi_api_for_user(user)
            for key in api.conversation_store.list_conversations():
                conv = api.get_wrapped_conversation(key)
                day = conv.created_at.date().replace(day=1)
                day_stats = date_stats.setdefault(day, defaultdict(int))
                self._increment_msg_stats(conv, day_stats)

        fields = ([
            "date", "conversations_started",
            "inbound_message_count", "outbound_message_count",
            "inbound_uniques", "outbound_uniques",
        ])
        writer = DictWriter(self.stdout, fields)
        writer.writerow(dict(zip(fields, fields)))
        for day in sorted(date_stats.iterkeys()):
            row = dict((f, 0) for f in fields)
            row["date"] = day.strftime("%m/%d/%Y")
            row.update(date_stats[day])
            writer.writerow(row)
