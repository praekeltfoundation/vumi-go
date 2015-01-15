from threading import Thread

from boto import connect_s3
from moto.s3 import s3_backend
from moto.server import create_backend_app, DomainDispatcherApplication
from werkzeug.serving import make_server
from zope.interface import implements

from vumi.tests.helpers import IHelper


class S3Helper(object):
    """
    Test helper for things that need to use S3.

    Using the test decorators `moto` provides is problematic, because they
    monkeypatch the `socket` module to intercept requests. This interferes with
    other network access, particularly to Redis. To get around this, we run the
    standalone server `moto` provides in a thread and patch our boto configs to
    use that as a proxy.

    We need access to a :class:`go.base.helpers.DjangoVumiApiHelper` so we can
    patch Django settings.
    """
    implements(IHelper)

    def __init__(self, vumi_helper):
        self.vumi_helper = vumi_helper
        self.server_thread = None
        self.server = None

    def setup(self):
        # Clear any leftover global state.
        s3_backend.reset()
        # Create a new server.
        self.server = self.make_server()
        # Run the server in a thread.
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def cleanup(self):
        if self.server is not None:
            # Tell the server to stop.
            self.server.shutdown()
        if self.server_thread is not None:
            # Wait for it to stop.
            self.server_thread.join()
        # Clear all the global state we modified.
        s3_backend.reset()

    def make_server(self):
        """
        Create a moto server object for S3.
        """
        main_app = DomainDispatcherApplication(create_backend_app, "s3")
        main_app.debug = True
        return make_server("localhost", 0, main_app, threaded=True)

    def patch_settings(self, config_name, **kw):
        """
        Patch the boto config in the Django settings.

        We set `proxy` and `proxy_port` to point to our background server and
        set `is_secure=False` so we can intercept the requests instead of
        actually proxying. (MitM attacks are an entirely reasonable testing
        tool.)
        """
        host, port = self.server.server_address
        defaults = {
            "aws_access_key_id": "AWS-DUMMY-ID",
            "aws_secret_access_key": "AWS-DUMMY-SECRET",
            "proxy": host,
            "proxy_port": port,
            "is_secure": False,
        }
        go_s3_buckets = {config_name: defaults}
        go_s3_buckets[config_name].update(kw)
        self.vumi_helper.patch_settings(GO_S3_BUCKETS=go_s3_buckets)

    def connect_s3(self):
        """
        Constuct a boto connection suitable for use in tests.
        """
        host, port = self.server.server_address
        return connect_s3(
            "AWS-DUMMY-ID", "AWS-DUMMY-SECRET", proxy=host, proxy_port=port,
            is_secure=False)
