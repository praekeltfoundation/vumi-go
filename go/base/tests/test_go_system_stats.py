# -*- coding: utf-8 -*-
from datetime import datetime

from go.vumitools.tests.helpers import GoMessageHelper, djangotest_imports

with djangotest_imports(globals()):
    from django.core.management.base import CommandError
    from django.core.management import call_command

    from go.base.tests.helpers import (
        GoDjangoTestCase, DjangoVumiApiHelper, CommandIO)


class TestGoSystemStatsCommand(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.msg_helper = self.add_helper(
            GoMessageHelper(vumi_helper=self.vumi_helper))

    def run_command(self, **kw):
        cmd_io = CommandIO()
        call_command('go_system_stats',
                     stdout=cmd_io.stdout, stderr=cmd_io.stderr, **kw)
        return cmd_io

    def mk_msgs_for_conv(self, conv, inbounds=(), outbounds=()):
        """ Utility for adding messages to a conversation.

        :param list inbounds:
            List of numbers of inbound messages to add. Each set of
            inbound messages reuses the same from_addr values which
            allows us to tweak the set of inbound uniques.

        :param list outbounds:
            List of numbers of outbound messages to add. Each set of
            outbound messages reuses the same to_addr values which
            allows us to tweak the set of outbound uniques.
        """
        for inbound in inbounds:
            self.msg_helper.add_inbound_to_conv(conv, inbound)
        for outbound in outbounds:
            self.msg_helper.add_outbound_to_conv(conv, outbound)

    def mk_conversations(self, **conv_types):
        """ Utility for making conversations in various statuses.

        :param dict conv_types:
            Mapping from conversation type to a list of status_descriptions.

        :param dict status_description:
            A dictionary with the keys count (how many conversations to
            create, default: 1), status (the conversation status, default:
            running), archive_status (default: active) and created_at (
            default: now).
        """
        for conv_type, conv_descs in conv_types.items():
            for conv_desc in conv_descs:
                for i in range(conv_desc.get('count', 1)):
                    conv = self.user_helper.create_conversation(
                        unicode(conv_type), name=u"%s_%d" % (conv_type, i),
                        status=unicode(conv_desc.get('status', 'running')),
                        archive_status=unicode(
                            conv_desc.get('archive_status', 'active')),
                        created_at=conv_desc.get(
                            'created_at', datetime.utcnow()))
                    self.mk_msgs_for_conv(
                        conv, inbounds=conv_desc.get('inbounds', ()),
                        outbounds=conv_desc.get('outbounds', ()))

    def assert_csv_output(self, cmd, rows):
        self.assertEqual(
            cmd.stdout.getvalue().split("\r\n"),
            rows + [""])
        self.assertEqual(cmd.stderr.getvalue(), "")

    def test_help(self):
        self.assertRaisesRegexp(
            CommandError,
            "^Please specify one of the following actions:"
            " --conversation-types"
            " --conversation-types-by-month"
            " --message-counts-by-month$",
            self.run_command)

    def test_conversation_types_no_conversations(self):
        cmd = self.run_command(command=["conversation_types"])
        self.assert_csv_output(cmd, [
            "type,total",
        ])

    def test_conversation_types(self):
        self.mk_conversations(
            bulk_message=[
                {"count": 3},
                {"count": 2, "archive_status": "archived"},
            ],
            jsbox=[
                {"count": 1, "status": "stopped"},
                {"count": 2},
            ],
        )
        cmd = self.run_command(command=["conversation_types"])
        self.assert_csv_output(cmd, [
            "type,total,running,stopped,active,archived",
            "bulk_message,5,3,0,3,2",
            "jsbox,3,2,1,3,0",
        ])

    def test_conversation_types_by_month_no_conversations(self):
        cmd = self.run_command(command=["conversation_types_by_month"])
        self.assert_csv_output(cmd, [
            "date",
        ])

    def test_conversation_types_by_month(self):
        days = [
            datetime(2013, m, d) for m, d in [
                (9, 1), (11, 1), (11, 5), (12, 2)
            ]]
        self.mk_conversations(
            bulk_message=[
                {"count": 3, "created_at": days[0]},
                {"count": 2, "created_at": days[1]},
            ],
            jsbox=[
                {"count": 1, "created_at": days[2]},
                {"count": 2, "created_at": days[3]},
            ],
        )

        cmd = self.run_command(command=["conversation_types_by_month"])
        self.assert_csv_output(cmd, [
            "date,bulk_message,jsbox",
            "09/01/2013,3,0",
            "11/01/2013,2,1",
            "12/01/2013,0,2",
        ])

    def test_message_counts_by_month_no_conversations(self):
        cmd = self.run_command(command=["message_counts_by_month"])
        self.assert_csv_output(cmd, [
            "date,conversations_started,"
            "inbound_message_count,outbound_message_count,"
            "inbound_uniques,outbound_uniques,total_uniques",
        ])

    def test_message_counts_by_month(self):
        days = [
            datetime(2013, m, d) for m, d in [
                (9, 1), (11, 1), (11, 5), (12, 2)
            ]]
        self.mk_conversations(
            bulk_message=[
                {"count": 1, "created_at": days[0],
                 "inbounds": [1, 1, 1], "outbounds": [2, 2, 2]},
                {"count": 2, "created_at": days[1],
                 "inbounds": [1], "outbounds": [1]},
            ],
            jsbox=[
                {"count": 1, "created_at": days[2]},
                {"count": 2, "created_at": days[3],
                 "inbounds": [1, 1], "outbounds": [3]},
            ],
        )

        cmd = self.run_command(command=["message_counts_by_month"])

        self.assert_csv_output(cmd, [
            "date,conversations_started,"
            "inbound_message_count,outbound_message_count,"
            "inbound_uniques,outbound_uniques,total_uniques",
            "09/01/2013,1,3,6,1,2,2",
            "11/01/2013,3,2,2,2,2,2",
            "12/01/2013,2,4,6,2,6,6",
        ])

    def test_custom_date_format(self):
        day = datetime(2013, 11, 1)
        self.mk_conversations(
            bulk_message=[
                {"count": 1, "created_at": day},
            ],
        )

        cmd = self.run_command(
            command=["conversation_types_by_month"], date_format="%Y-%m-%d")
        self.assert_csv_output(cmd, [
            "date,bulk_message",
            "2013-11-01,1",
        ])
