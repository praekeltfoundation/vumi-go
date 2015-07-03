""" Retrieve stats on the Vumi Go system. """

from collections import defaultdict
from csv import DictWriter
from optparse import make_option

from go.base.command_utils import BaseGoCommand, get_users, make_command_option


class StatsWriter(DictWriter):
    """ Helper for writing stats out as CSV. """
    def __init__(self, file_obj, fields, default=0):
        DictWriter.__init__(self, file_obj, fields)
        self.fields = fields
        self.defaults = dict((f, default) for f in fields)

    def writeheader(self):
        DictWriter.writerow(self, dict(zip(self.fields, self.fields)))

    def writerow(self, data):
        row = self.defaults.copy()
        row.update(data)
        DictWriter.writerow(self, row)


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
                " month.")),
        make_command_option(
            'message_counts_by_month',
            help=(
                "Inbound and outbound message counts and total unique users"
                " by month and conversation type.")),
        make_option(
            '--date-format', dest='date_format', default='%m/%d/%Y',
            help=(
                "Output format for dates. Defaults to '%m/%d/%Y' which is"
                " understood by Google Spreadsheet's importer."))
    )

    def _format_date(self, date):
        return date.strftime(self.options['date_format'])

    def handle_command_conversation_types(self, *args, **options):
        conv_types = set()
        conv_statuses = set()
        conv_archive_statuses = set()
        type_stats = {}

        for user in get_users():
            api = self.user_api_for_user(user)
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
        writer = StatsWriter(self.stdout, fields)
        writer.writeheader()
        for conv_type in sorted(conv_types):
            row = {"type": conv_type}
            row.update(type_stats[conv_type])
            writer.writerow(row)

    def handle_command_conversation_types_by_month(self, *args, **options):
        conv_types = set()
        month_stats = {}

        for user in get_users():
            api = self.user_api_for_user(user)
            for key in api.conversation_store.list_conversations():
                conv = api.get_wrapped_conversation(key)
                conv_types.add(conv.conversation_type)
                month = conv.created_at.date().replace(day=1)
                stats = month_stats.setdefault(month, defaultdict(int))
                stats[conv.conversation_type] += 1

        fields = (["date"] + sorted(conv_types))
        writer = StatsWriter(self.stdout, fields)
        writer.writeheader()
        for month in sorted(month_stats.iterkeys()):
            row = {"date": self._format_date(month)}
            row.update(month_stats[month])
            writer.writerow(row)

    def _increment_msg_stats(self, conv, stats):
        inbound_stats = conv.FIXME_mdb.batch_inbound_stats(conv.batch.key)
        outbound_stats = conv.FIXME_mdb.batch_outbound_stats(conv.batch.key)
        stats["conversations_started"] += 1
        stats["inbound_message_count"] += inbound_stats['total']
        stats["outbound_message_count"] += outbound_stats['total']
        stats["inbound_uniques"] += inbound_stats['unique_addresses']
        stats["outbound_uniques"] += outbound_stats['unique_addresses']
        stats["total_uniques"] += max(
            inbound_stats['unique_addresses'],
            outbound_stats['unique_addresses'])

    def handle_command_message_counts_by_month(self, *args, **options):
        month_stats = {}

        for user in get_users():
            api = self.user_api_for_user(user)
            for key in api.conversation_store.list_conversations():
                conv = api.get_wrapped_conversation(key)
                month = conv.created_at.date().replace(day=1)
                stats = month_stats.setdefault(month, defaultdict(int))
                self._increment_msg_stats(conv, stats)

        fields = ([
            "date", "conversations_started",
            "inbound_message_count", "outbound_message_count",
            "inbound_uniques", "outbound_uniques", "total_uniques",
        ])
        writer = StatsWriter(self.stdout, fields)
        writer.writeheader()
        for month in sorted(month_stats.iterkeys()):
            row = {"date": self._format_date(month)}
            row.update(month_stats[month])
            writer.writerow(row)
