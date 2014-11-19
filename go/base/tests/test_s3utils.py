""" Tests for go.base.s3utils. """

from moto import mock_s3

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper

from go.base.s3utils import BucketConfig, Bucket


class TestBucketConfig(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())

    def mk_config(self, **kw):
        self.vumi_helper.patch_settings(GO_S3_BUCKETS=kw)

    def test_custom_value_with_defaults(self):
        self.mk_config(defaults={'foo': 'bar'}, custom={'foo': 'baz'})
        self.assertEqual(BucketConfig('custom').foo, 'baz')

    def test_custom_value_no_defaults(self):
        self.mk_config(custom={'foo': 'baz'})
        self.assertEqual(BucketConfig('custom').foo, 'baz')

    def test_default_value_with_custom_config(self):
        self.mk_config(defaults={'foo': 'bar'}, custom={})
        self.assertEqual(BucketConfig('custom').foo, 'bar')

    def test_default_value_no_custom_config(self):
        self.mk_config(defaults={'foo': 'bar'})
        self.assertEqual(BucketConfig('custom').foo, 'bar')

    def test_missing_value(self):
        self.mk_config(defaults={'foo': 'bar'}, custom={'foo': 'baz'})
        b = BucketConfig('custom')
        self.assertRaisesRegexp(
            AttributeError, "BucketConfig 'custom' has no attribute 'unknown'",
            getattr, b, 'unknown')

    def test_missing_bucket(self):
        self.mk_config(defaults={'foo': 'bar'})
        b = BucketConfig('custom')
        self.assertRaisesRegexp(
            AttributeError, "BucketConfig 'custom' has no attribute 'unknown'",
            getattr, b, 'unknown')

    def test_blank_config(self):
        self.mk_config()
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
    @mock_s3
    def test_get_s3_bucket(self):
        pass

    @mock_s3
    def test_upload(self):
        pass
