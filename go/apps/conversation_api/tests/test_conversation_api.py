from twisted.internet.defer import inlineCallbacks

from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.conversation_api import ConversationApiWorker


class ConversationApiTestCase(AppWorkerTestCase):

    use_riak = True
    application_class = ConversationApiWorker

    @inlineCallbacks
    def setUp(self):
        yield super(ConversationApiTestCase, self).setUp()
        config = self.mk_config({
            'worker_name': 'conversation_api_worker',
            'web_path': '/foo/',
            'web_port': 0,
            'health_path': '/health/',
        })
        self.app = yield self.get_application(config)
        addr = self.app.webserver.getHost()
        self.url = 'http://%s:%s/' % (addr.host, addr.port)

    def test_foo(self):
        print self.url
