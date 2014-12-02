""" Utilities for dealing with uploading to S3. """

import StringIO
import gzip

import boto

from django.conf import settings


class BucketConfig(object):
    """ Helper for accessing Django GO_S3_BUCKET settings. """

    def __init__(self, config_name):
        self.config_name = config_name

    def __getattr__(self, name):
        bucket_config = settings.GO_S3_BUCKETS.get(self.config_name, {})
        defaults = settings.GO_S3_BUCKETS.get('defaults', {})
        if name in bucket_config:
            return bucket_config[name]
        if name in defaults:
            return defaults[name]
        raise AttributeError(
            "BucketConfig %r has no attribute %r" % (self.config_name, name))


class MultipartWriter(object):
    """ Helper for writing pending chunks of data. """
    def __init__(self, minimum_size=5 * 1024 * 1024):
        self.minimum_size = minimum_size
        self._clear_pending()

    def _clear_pending(self):
        self._pending = []
        self._pending_size = 0

    def _ready(self):
        return self._pending_size >= self.minimum_size

    def _empty(self):
        return not bool(self._pending)

    def _push_chunk(self, chunk):
        self._pending.append(chunk)
        self._pending_size += len(chunk)

    def _pop_part(self):
        fp = StringIO.StringIO("".join(self._pending))
        self._clear_pending()
        return fp

    def push_chunks(self, chunks):
        for chunk in chunks:
            self._push_chunk(chunk)
            if self._ready():
                yield self._pop_part()
        if not self._empty():
            yield self._pop_part()


class GzipMultipartWriter(object):
    """ Helper for tracking and compressing pending chunks of data. """
    def __init__(self, minimum_size=5 * 1024 * 1024):
        self.minimum_size = minimum_size
        self._string_file = StringIO.StringIO()
        self._gzip_file = gzip.GzipFile(fileobj=self._string_file, mode='w')

    def _clear_pending(self):
        self._string_file.seek(0)
        self._string_file.truncate()

    def _ready(self):
        return self._string_file.tell() >= self.minimum_size

    def _empty(self):
        return not bool(self._string_file.tell())

    def _pop_part(self):
        fp = StringIO.StringIO(self._string_file.getvalue())
        self._clear_pending()
        return fp

    def push_chunks(self, chunks):
        for chunk in chunks:
            self._gzip_file.write(chunk)
            if self._ready():
                yield self._pop_part()
        self._gzip_file.close()
        if not self._empty():
            yield self._pop_part()


class Bucket(object):
    """ An S3 bucket.

    :param str config_name:
        The name of the bucket config.

    Bucket configuration is defined via Django settings as follows:

    ::

       GO_S3_BUCKETS = {
           'defaults': {
               'aws_access_key_id': 'MY-ACCESS-KEY-ID',
               'aws_secret_access_key': 'SECRET',
           },
           'billing.archive': {
               's3_bucket_name': 'go.vumi.org.billing.archive',
           },
       }

    """

    def __init__(self, config_name):
        self.config = BucketConfig(config_name)

    def _s3_conn(self):
        return boto.connect_s3(
            self.config.aws_access_key_id, self.config.aws_secret_access_key)

    def get_s3_bucket(self):
        """ Return an S3 bucket object. """
        conn = self._s3_conn()
        return conn.get_bucket(self.config.s3_bucket_name)

    def create(self):
        """ Create the S3 bucket. """
        conn = self._s3_conn()
        return conn.create_bucket(self.config.s3_bucket_name)

    def upload(self, key_name, chunks, headers=None, gzip=False):
        """ Upload chunks of data to S3. """
        bucket = self.get_s3_bucket()
        mp = bucket.initiate_multipart_upload(key_name, headers=headers)

        if gzip:
            writer = GzipMultipartWriter()
        else:
            writer = MultipartWriter()

        try:
            for part_num, part in enumerate(writer.push_chunks(chunks)):
                mp.upload_part_from_file(part, part_num=part_num + 1)
        except:
            mp.cancel_upload()
            raise
        else:
            mp.complete_upload()
