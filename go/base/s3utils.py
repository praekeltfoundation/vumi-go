""" Utilities for dealing with uploading to S3. """

import StringIO
import gzip

import boto

from django.conf import settings

from zope.interface import Interface, implements

from go.errors import VumiGoError


class BucketError(VumiGoError):
    """ Raised when an error occurs during an operation on a bucket. """


class KeyAlreadyExistsError(BucketError):
    """ Raised when an S3 key unexpectedly already exists. """


class BucketConfig(object):
    """ Helper for accessing Django GO_S3_BUCKET settings. """

    def __init__(self, config_name):
        self.config_name = config_name

    def __getattr__(self, name):
        bucket_config = settings.GO_S3_BUCKETS.get(self.config_name, {})
        # We set defaults for "proxy", "proxy_port", and "is_secure" because we
        # override them in tests to use an in-process moto fake instead of
        # hitting S3 for real.
        defaults = {
            "proxy": None,
            "proxy_port": None,
            "is_secure": True,
        }
        defaults.update(settings.GO_S3_BUCKETS.get('defaults', {}))
        if name in bucket_config:
            return bucket_config[name]
        if name in defaults:
            return defaults[name]
        raise AttributeError(
            "BucketConfig %r has no attribute %r" % (self.config_name, name))


class IMultipartWriter(Interface):
    def push_chunks(chunks):
        """
        Push an iterator over chunks of data and yield files for multipart
        uploading.

        :param iter chunks:
            An iterator over chunks of bytes.

        :returns iter:
            Returns an iterator over file-like objects, each of which is
            a file part to upload.
        """


class MultipartWriter(object):
    """ Helper for writing pending chunks of data. """

    implements(IMultipartWriter)

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

    implements(IMultipartWriter)

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
            self.config.aws_access_key_id, self.config.aws_secret_access_key,
            proxy=self.config.proxy, proxy_port=self.config.proxy_port,
            is_secure=self.config.is_secure)

    def get_s3_bucket(self):
        """ Return an S3 bucket object. """
        conn = self._s3_conn()
        return conn.get_bucket(self.config.s3_bucket_name)

    def create(self):
        """ Create the S3 bucket. """
        conn = self._s3_conn()
        return conn.create_bucket(self.config.s3_bucket_name)

    def upload(self, key_name, chunks, headers=None, metadata=None,
               gzip=False, replace=False):
        """ Upload chunks of data to S3.

        :param str key_name:
            Key to upload to.

        :param iter chunks:
            Iterator over chunks of bytes to upload.

        :param dict headers:
            Dictionary of HTTP headers to upload with the file.

        :param dict metadata:
            Dictionary of S3 metadata to upload with the file.
            Content-Type and Content-Encoding are copied from ``headers``.

        :param bool gzip:
            Whether to gzip the data before uploading it. Automatically
            sets the Content-Encoding to ``gzip``.

        :param bool replace:
            Whether to allow an existing file to be replaced.
        """
        bucket = self.get_s3_bucket()
        if headers is None:
            headers = {}
        if metadata is None:
            metadata = {}

        if gzip:
            writer = GzipMultipartWriter()
            headers['Content-Encoding'] = 'gzip'
        else:
            writer = MultipartWriter()

        for field in ('Content-Type', 'Content-Encoding'):
            if field in headers:
                metadata[field] = headers[field]

        if not replace and bucket.get_key(key_name) is not None:
            raise KeyAlreadyExistsError(
                "Key %r already exists in bucket %r" % (key_name, bucket.name))

        mp = bucket.initiate_multipart_upload(
            key_name, headers=headers, metadata=metadata)
        try:
            for part_num, part in enumerate(writer.push_chunks(chunks)):
                mp.upload_part_from_file(part, part_num=part_num + 1)
        except:
            mp.cancel_upload()
            raise
        else:
            mp.complete_upload()
