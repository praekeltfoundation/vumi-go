# -*- coding: utf-8 -*-
"""Test for go.base.tests.s3_helpers."""

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.base.tests.s3_helpers import S3Helper


class TestS3Helper(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())

    def test_setup_cleanup_server_lifecycle(self):
        """
        Helper setup starts a moto server and helper cleanup stops it.
        """
        s3_helper = S3Helper(self.vumi_helper)
        self.add_cleanup(s3_helper.cleanup)
        self.assertEqual(s3_helper.server, None)

        s3_helper.setup()
        self.assertNotEqual(s3_helper.server, None)
        self.assertEqual(s3_helper.server_thread.is_alive(), True)

        s3_client = s3_helper.connect_s3()
        self.assertEqual(s3_client.get_all_buckets(), [])

        s3_helper.cleanup()
        self.assertEqual(s3_helper.server_thread.is_alive(), False)
        # We can't check that the server is no longer listening because there's
        # no sane way to give boto suitable retry and timeout values.

    def test_cleanup_when_not_running(self):
        """
        Helper is should be safe to call before setup and after setup+cleanup.
        """
        s3_helper = S3Helper(self.vumi_helper)
        self.add_cleanup(s3_helper.cleanup)

        self.assertEqual(s3_helper.server, None)
        s3_helper.cleanup()
        self.assertEqual(s3_helper.server, None)

        s3_helper.setup()
        self.assertEqual(s3_helper.server_thread.is_alive(), True)
        s3_helper.cleanup()
        self.assertEqual(s3_helper.server_thread.is_alive(), False)
        s3_helper.cleanup()
        self.assertEqual(s3_helper.server_thread.is_alive(), False)

    def test_setup_cleanup_resets_server_state(self):
        """
        Helper setup and cleanup reset server state so tests aren't coupled
        through S3.
        """
        s3_helper = S3Helper(self.vumi_helper)
        self.add_cleanup(s3_helper.cleanup)
        s3_helper.setup()

        s3_client = s3_helper.connect_s3()
        self.assertEqual(s3_client.get_all_buckets(), [])
        s3_client.create_bucket("mybucket")
        self.assertNotEqual(s3_client.get_all_buckets(), [])

        s3_helper.cleanup()
        s3_helper.setup()
        s3_client = s3_helper.connect_s3()
        self.assertEqual(s3_client.get_all_buckets(), [])

    def test_patch_settings_defaults(self):
        """
        When we patch settings, the default values are applied.
        """
        s3_helper = self.add_helper(S3Helper(self.vumi_helper))
        host, port = s3_helper.server.server_address

        from django.conf import settings
        self.vumi_helper.patch_settings(GO_S3_BUCKETS={})
        self.assertEqual(settings.GO_S3_BUCKETS, {})

        s3_helper.patch_settings("foo")
        self.assertEqual(settings.GO_S3_BUCKETS, {"foo": {
            "aws_access_key_id": "AWS-DUMMY-ID",
            "aws_secret_access_key": "AWS-DUMMY-SECRET",
            "proxy": host,
            "proxy_port": port,
            "is_secure": False,
        }})

    def test_patch_settings_override(self):
        """
        When we patch settings, the default values can be overridden.
        """
        s3_helper = self.add_helper(S3Helper(self.vumi_helper))
        host, port = s3_helper.server.server_address

        from django.conf import settings
        self.vumi_helper.patch_settings(GO_S3_BUCKETS={})
        self.assertEqual(settings.GO_S3_BUCKETS, {})

        s3_helper.patch_settings("foo", aws_access_key_id="SEEKRIT", bar="baz")
        self.assertEqual(settings.GO_S3_BUCKETS, {"foo": {
            "aws_access_key_id": "SEEKRIT",
            "aws_secret_access_key": "AWS-DUMMY-SECRET",
            "proxy": host,
            "proxy_port": port,
            "is_secure": False,
            "bar": "baz",
        }})

    def test_connect_s3(self):
        """
        We can get an S3 connection that talks to our fake server.
        """
        s3_helper = self.add_helper(S3Helper(self.vumi_helper))

        s3_client_1 = s3_helper.connect_s3()
        s3_client_2 = s3_helper.connect_s3()
        self.assertNotEqual(s3_client_1, s3_client_2)

        self.assertEqual(s3_client_1.get_all_buckets(), [])
        s3_client_2.create_bucket("mybucket")
        self.assertEqual(
            [b.name for b in s3_client_1.get_all_buckets()], ["mybucket"])
