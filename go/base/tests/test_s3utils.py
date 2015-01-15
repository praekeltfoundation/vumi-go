""" Tests for go.base.s3utils. """

import gzip
import md5
import StringIO

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.base.tests.s3_helpers import S3Helper

from go.base.s3utils import (
    BucketConfig, Bucket, IMultipartWriter,
    MultipartWriter, GzipMultipartWriter,
    KeyAlreadyExistsError)


def gunzip(data):
    """ Gunzip data. """
    return gzip.GzipFile(fileobj=StringIO.StringIO(data)).read()


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


class TestMultipartWriter(GoDjangoTestCase):
    def _push_chunks(self, writer, chunks):
        return [part.getvalue() for part in writer.push_chunks(chunks)]

    def test_implements_IMultipartWriter(self):
        self.assertTrue(IMultipartWriter.providedBy(MultipartWriter()))

    def test_push_chunks(self):
        writer = MultipartWriter(minimum_size=5)
        parts = self._push_chunks(writer, ["abab", "c", "bcd"])
        self.assertEqual(parts, ["ababc", "bcd"])

    def test_push_chunks_splits_second_part_correctly(self):
        writer = MultipartWriter(minimum_size=5)
        parts = self._push_chunks(writer, ["abab", "c", "abab", "c", "b"])
        self.assertEqual(parts, ["ababc", "ababc", "b"])

    def test_push_chunks_empty(self):
        writer = MultipartWriter(minimum_size=5)
        parts = self._push_chunks(writer, [])
        self.assertEqual(parts, [])


class TestGzipMultipartWriter(GoDjangoTestCase):
    def _push_chunks(self, writer, chunks):
        return [part.getvalue() for part in writer.push_chunks(chunks)]

    def _decode_parts(self, parts):
        return gunzip("".join(parts))

    def test_implements_IMultipartWriter(self):
        self.assertTrue(IMultipartWriter.providedBy(GzipMultipartWriter()))

    def test_push_chunks(self):
        writer = GzipMultipartWriter(minimum_size=5)
        parts = self._push_chunks(writer, ["abab", "c", "bcd"])
        self.assertEqual(self._decode_parts(parts), "ababcbcd")
        self.assertEqual(len(parts), 2)

    def test_push_chunks_splits_second_part_correctly(self):
        writer = GzipMultipartWriter(minimum_size=5)

        # This generates a fixed pseudo random sequence that is hard for gzip
        # to compress so we can get multiple parts without a huge data set.

        def chunk(i, j):
            return md5.md5(chr(i) + chr(j)).hexdigest()
        chunks = [chunk(i, j) for i in range(40) for j in range(40)]

        parts = self._push_chunks(writer, chunks)
        self.assertEqual(self._decode_parts(parts), "".join(chunks))
        self.assertEqual(len(parts), 3)

    def test_push_chunks_empty(self):
        writer = MultipartWriter(minimum_size=5)
        parts = self._push_chunks(writer, [])
        self.assertEqual(self._decode_parts(parts), "")
        self.assertEqual(len(parts), 0)


class TestBucket(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.s3_helper = self.add_helper(S3Helper(self.vumi_helper))

    def mk_bucket(self, config_name, **kw):
        self.s3_helper.patch_settings(config_name, **kw)
        return Bucket(config_name)

    def get_s3_bucket(self, name):
        conn = self.s3_helper.connect_s3()
        return conn.get_bucket(name)

    def create_s3_bucket(self, name):
        conn = self.s3_helper.connect_s3()
        conn.create_bucket(name)

    def list_s3_buckets(self):
        conn = self.s3_helper.connect_s3()
        return [b.name for b in conn.get_all_buckets()]

    def test_get_s3_bucket(self):
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        b = bucket.get_s3_bucket()
        self.assertEqual(b.name, 's3_custom')

    def test_create(self):
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        self.assertEqual(self.list_s3_buckets(), [])
        bucket.create()
        self.assertEqual(self.list_s3_buckets(), ["s3_custom"])

    def test_upload_single_part(self):
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        bucket.upload("my.key", ["chunk1:", "chunk2:", "chunk3"])
        s3_bucket = self.get_s3_bucket('s3_custom')
        self.assertEqual(s3_bucket.get_all_multipart_uploads(), [])
        [s3_key] = s3_bucket.get_all_keys()
        self.assertEqual(
            s3_key.get_contents_as_string(), "chunk1:chunk2:chunk3")

    def test_upload_headers(self):
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        bucket.upload(
            "my.key", ["chunk1"], headers={
                "Content-Type": "text/xml; charset=latin-1"})
        s3_bucket = self.get_s3_bucket('s3_custom')
        s3_key = s3_bucket.get_key('my.key')
        # moto doesn't currently track content type for multipart
        # uploads -- see https://github.com/spulec/moto/issues/274
        # TODO: uncomment when #274 is released.
        # self.assertEqual(
        #     s3_key.content_type, "text/xml; charset=latin-1")

    def _patch_s3_key_buffer_size(self, size=1024 * 1024):
        # the default BufferSize is tiny (8KB) and gives terrible
        # performance in tests with largish (e.g. 6MB) data sets. This
        # tweak improves test run time by a factor of ~30 (6s -> 0.2s).
        from boto.s3.key import Key
        self.monkey_patch(Key, 'BufferSize', size)

    def test_upload_multiple_parts(self):
        self._patch_s3_key_buffer_size()
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

    def test_upload_part_fails(self):
        def bad_parts():
            yield "chunk1"
            yield "chunk2"
            raise Exception("Failed")
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        self.assertRaisesRegexp(
            Exception, "Failed",
            bucket.upload, "my.key", bad_parts())
        s3_bucket = self.get_s3_bucket('s3_custom')
        self.assertEqual(s3_bucket.get_all_multipart_uploads(), [])
        self.assertEqual(s3_bucket.get_all_keys(), [])

    def test_upload_gzip(self):
        self.create_s3_bucket('s3_custom')
        data = "ab" * (3 * 1024)  # 6KB

        def chunks(data=data, chunk_size=200):
            for i in xrange(0, len(data), chunk_size):
                yield data[i:i + chunk_size]

        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        bucket.upload("my.key", chunks(), gzip=True)
        s3_bucket = self.get_s3_bucket('s3_custom')
        self.assertEqual(s3_bucket.get_all_multipart_uploads(), [])
        [s3_key] = s3_bucket.get_all_keys()

        s3_data = s3_key.get_contents_as_string()
        self.assertEqual(gunzip(s3_data), data)

    def test_upload_gzip_headers(self):
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        bucket.upload(
            "my.key", ["chunk1"], gzip=True)
        s3_bucket = self.get_s3_bucket('s3_custom')
        s3_key = s3_bucket.get_key('my.key')
        # moto doesn't currently track content encoding for multipart
        # uploads -- see https://github.com/spulec/moto/issues/274
        # TODO: uncomment when #274 is released.
        # self.assertEqual(
        #     s3_key.content_encoding, "gzip")

    def test_upload_to_existing_key_fails(self):
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        s3_bucket = self.get_s3_bucket('s3_custom')
        s3_key = s3_bucket.new_key('my.key')
        s3_key.set_contents_from_string("box of chocolates")
        self.assertRaisesRegexp(
            KeyAlreadyExistsError,
            "Key 'my.key' already exists in bucket 's3_custom'",
            bucket.upload, "my.key", ["chunk"])

        [s3_key] = s3_bucket.get_all_keys()
        self.assertEqual(s3_key.get_contents_as_string(), "box of chocolates")

    def test_upload_to_existing_key_succeeds_if_replace_is_true(self):
        self.create_s3_bucket('s3_custom')
        bucket = self.mk_bucket('custom', s3_bucket_name='s3_custom')
        s3_bucket = self.get_s3_bucket('s3_custom')
        s3_key = s3_bucket.new_key('my.key')
        s3_key.set_contents_from_string("bags of coffee")
        bucket.upload("my.key", ["chunk"], replace=True)

        [s3_key] = s3_bucket.get_all_keys()
        self.assertEqual(s3_key.get_contents_as_string(), "chunk")
