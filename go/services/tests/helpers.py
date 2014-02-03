import os

from zope.interface import implements

from vumi.tests.helpers import generate_proxies, IHelper

from django.core.files.uploadedfile import UploadedFile

from go.base.tests.helpers import DjangoVumiApiHelper


class FakeUploadedFile(UploadedFile):

    def __init__(self, sample_file, content_type=None):
        super(FakeUploadedFile, self).__init__(
            sample_file, sample_file.name, content_type,
            os.path.getsize(sample_file.name), None)

    def temporary_file_path(self):
        return self.file.name

    def close(self):
        try:
            return self.file.close()
        except OSError:
            pass


class ServiceHelper(object):
    implements(IHelper)

    def __init__(self, vumi_helper):
        self.is_sync = vumi_helper.is_sync
        self.vumi_helper = vumi_helper

    def setup(self):
        pass

    def cleanup(self):
        pass


class ServiceViewHelper(object):
    implements(IHelper)

    def __init__(self):
        self.vumi_helper = DjangoVumiApiHelper()
        self._service_helper = ServiceHelper(self.vumi_helper)

        generate_proxies(self, self._service_helper)
        generate_proxies(self, self.vumi_helper)

    def setup(self):
        # Create the things we need to create
        self.vumi_helper.setup()
        self.vumi_helper.make_django_user()

    def cleanup(self):
        return self.vumi_helper.cleanup()
