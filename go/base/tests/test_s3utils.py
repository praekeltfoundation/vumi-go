""" Tests for go.base.s3utils. """

from moto import mock_s3

from go.base.tests.helpers import GoDjangoTestCase

from go.base.s3utils import BucketConfig, Bucket


class TestBucketConfig(GoDjangoTestCase):
    def test_custom_value(self):
        pass

    def test_default_value(self):
        pass

    def test_missing_value(self):
        pass

    def test_missing_bucket(self):
        pass


class TestBucket(GoDjangoTestCase):
    @mock_s3
    def test_get_s3_bucket(self):
        pass

    @mock_s3
    def test_upload(self):
        pass
