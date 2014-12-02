""" Tests for go.base.s3utils. """

import boto
import moto

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper

from go.base.s3utils import BucketConfig, Bucket


class TestBucketConfig(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())

    def patch_s3_settings(self, **kw):
        self.vumi_helper.patch_settings(GO_S3_BUCKETS=kw)

    def test_custom_value_with_defaults(self):
        self.patch_s3_settings(defaults={'foo': 'bar'}, custom={'foo': 'baz'})
        self.assertEqual(BucketConfig('custom').foo, 'baz')

    def test_custom_value_no_defaults(self):
        self.patch_s3_settings(custom={'foo': 'baz'})
        self.assertEqual(BucketConfig('custom').foo, 'baz')

    def test_default_value_with_custom_config(self):
        self.patch_s3_settings(defaults={'foo': 'bar'}, custom={})
        self.assertEqual(BucketConfig('custom').foo, 'bar')

    def test_default_value_no_custom_config(self):
        self.patch_s3_settings(defaults={'foo': 'bar'})
        self.assertEqual(BucketConfig('custom').foo, 'bar')

    def test_missing_value(self):
        self.patch_s3_settings(defaults={'foo': 'bar'}, custom={'foo': 'baz'})
        b = BucketConfig('custom')
        self.assertRaisesRegexp(
            AttributeError, "BucketConfig 'custom' has no attribute 'unknown'",
            getattr, b, 'unknown')

    def test_missing_bucket(self):
        self.patch_s3_settings(defaults={'foo': 'bar'})
        b = BucketConfig('custom')
        self.assertRaisesRegexp(
            AttributeError, "BucketConfig 'custom' has no attribute 'unknown'",
            getattr, b, 'unknown')

    def test_blank_config(self):
        self.patch_s3_settings()
        b = BucketConfig('custom')
        self.assertRaisesRegexp(
            AttributeError, "BucketConfig 'custom' has no attribute 'unknown'",
            getattr, b, 'unknown')

    def test_no_config(self):
        b = BucketConfig('custom')
        self.assertRaisesRegexp(
            AttributeError,
            "'Settings' object has no attribute 'GO_S3_BUCKETS'",
            getattr, b, 'unknown')


class TestBucket(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())

    def mk_bucket(self, config_name, defaults=None, **kw):
        if defaults is None:
            defaults = {
                "aws_access_key_id": "AWS-DUMMY-ID",
                "aws_secret_access_key": "AWS-DUMMY-SECRET",
            }
        go_s3_buckets = {config_name: defaults}
        go_s3_buckets[config_name].update(kw)
        self.vumi_helper.patch_settings(GO_S3_BUCKETS=go_s3_buckets)
        return Bucket(config_name)

    def get_s3_bucket(self, name):
        conn = boto.connect_s3()
        return conn.get_bucket(name)

    def create_s3_bucket(self, name):
        conn = boto.connect_s3()
        conn.create_bucket(name)

    def list_s3_buckets(self):
        conn = boto.connect_s3()
        return [b.name for b in conn.get_all_buckets()]

    @moto.mock_s3
    def test_get_s3_bucket(self):
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        b = bucket.get_s3_bucket()
        self.assertEqual(b.name, 's3_custom')

    @moto.mock_s3
    def test_create(self):
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        self.assertEqual(self.list_s3_buckets(), [])
        bucket.create()
        self.assertEqual(self.list_s3_buckets(), ["s3_custom"])

    @moto.mock_s3
    def test_upload_single_part(self):
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        bucket.upload("my.key", ["chunk1:", "chunk2:", "chunk3"])
        s3_bucket = self.get_s3_bucket('s3_custom')
        self.assertEqual(s3_bucket.get_all_multipart_uploads(), [])
        [s3_key] = s3_bucket.get_all_keys()
        self.assertEqual(
            s3_key.get_contents_as_string(), "chunk1:chunk2:chunk3")

    @moto.mock_s3
    def test_upload_multiple_parts(self):
        self.create_s3_bucket('s3_custom')
        data = "ab" * (3 * 1024 * 1024)  # ~ 6MB

        def chunks(data=data, chunk_size=200):
            for i in xrange(0, len(data), chunk_size):
                yield data[i:i + chunk_size]

        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        bucket.upload("my.key", chunks())
        s3_bucket = self.get_s3_bucket('s3_custom')
        self.assertEqual(s3_bucket.get_all_multipart_uploads(), [])
        [s3_key] = s3_bucket.get_all_keys()
        self.assertEqual(s3_key.get_contents_as_string(), data)
