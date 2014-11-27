""" Utilities for dealing with uploading to S3. """

import StringIO

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


class MultipartPusher(object):
    """ Helper for tracking pending chunks of data. """
    def __init__(self, mp, minimum_size=5*1024*1024):
        self.mp = mp
        self.minimum_size = minimum_size
        self.part_num = 0
        self.clear_pending()

    def clear_pending(self):
        self._pending = []
        self._pending_size = 0

    def ready(self):
        return self._pending_size >= self.minimum_size

    def empty(self):
        return not bool(self._pending)

    def push_chunk(self, chunk):
        self._pending.append(chunk)
        self._pending_size += len(chunk)
        if self.ready():
            self.push_part()

    def push_done(self):
        if not self.empty():
            self.push_part()

    def pop_part(self):
        self.part_num += 1
        fp = StringIO.StringIO("".join(self._pending))
        self.clear_pending()
        return fp, self.part_num

    def push_part(self):
        fp, part_num = self.pop_part()
        self.mp.upload_part_from_file(fp, part_num=part_num)


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

    def upload(self, key_name, chunks, headers=None):
        """ Upload chunks of data to S3. """
        bucket = self.get_s3_bucket()
        mp = bucket.initiate_multipart_upload(key_name, headers=headers)
        pusher = MultipartPusher(mp)
        try:
            for chunk in chunks:
                pusher.push_chunk(chunk)
            pusher.push_done()
        except:
            mp.cancel_upload()
            raise
        else:
            mp.complete_upload()
