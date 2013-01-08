from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.utils import ApplicationTestCase

from go.apps.http_api.vumi_app import StreamingHTTPWorker


class StreamingHTTPWorkerTestCase(ApplicationTestCase):

    application_class = StreamingHTTPWorker

    @inlineCallbacks
    def setUp(self):
        yield super(StreamingHTTPWorkerTestCase, self).setUp()
        self.app = yield self.get_application({
            'web_path': '/foo',
            'web_port': 0,
            })

    def test_something(self):
        print self.app.webserver
