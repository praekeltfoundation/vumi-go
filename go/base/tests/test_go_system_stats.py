# -*- coding: utf-8 -*-
from StringIO import StringIO

from django.core.management.base import CommandError

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.base.management.commands import go_system_stats


class TestGoSystemStatsCommand(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.redis = self.vumi_helper.get_vumi_api().redis

    def run_command(self, **kw):
        command = go_system_stats.Command()
        command.stdout = StringIO()
        command.stderr = StringIO()
        command.handle(**kw)
        return command

    def mk_conversations(self, **conv_types):
        """ Utility for making conversations in various statuses.

        :param dict conv_types:
            Mapping from conversation type to a list of status_descriptions.

        :param dict status_description:
            A dictionary with the keys count (how many conversations to
            create, default: 1), status (the conversation status, default:
            running) and archive_status (default: active).
        """
        for conv_type, conv_descs in conv_types.items():
            for conv_desc in conv_descs:
                for i in range(conv_desc.get('count', 1)):
                    self.user_helper.create_conversation(
                        unicode(conv_type), name=u"%s_%d" % (conv_type, i),
                        status=unicode(conv_desc.get('status', 'running')),
                        archive_status=unicode(
                            conv_desc.get('archive_status', 'active')))

    def test_help(self):
        self.assertRaisesRegexp(
            CommandError,
            "^Please specify one of the following actions:"
            " --conversation-types"
            " --conversation-types-by-date"
            " --message-counts-by-date$",
            self.run_command)

    def test_conversation_types_no_conversations(self):
        cmd = self.run_command(command=["conversation_types"])
        self.assertEqual(cmd.stdout.getvalue().split("\r\n"), [
            "type,total",
            "",
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
        self.assertEqual(cmd.stdout.getvalue().split("\r\n"), [
            "type,total,running,stopped,active,archived",
            "bulk_message,5,3,0,3,2",
            "jsbox,3,2,1,3,0",
            ""
        ])

    def test_conversation_types_by_date_no_conversations(self):
        self.assertRaisesRegexp(
            NotImplementedError,
            "conversation_types_by_date not yet implemented",
            self.run_command, command=["conversation_types_by_date"])

    def test_message_counts_by_date_no_conversations(self):
        self.assertRaisesRegexp(
            NotImplementedError,
            "counts_by_date not yet implemented",
            self.run_command, command=["message_counts_by_date"])
