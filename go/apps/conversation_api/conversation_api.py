# -*- test-case-name: go.apps.conversation_api.tests.test_conversation_api -*-

from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import inlineCallbacks, Deferred

from vumi.config import ConfigText, ConfigDict, ConfigInt
from vumi.transports.httprpc import httprpc

from go.apps.http_api.resource import AuthorizedResource, BaseResource
from go.vumitools.app_worker import GoApplicationWorker
from go.vumitools.api import VumiApi


class ConversationApiResource(BaseResource):

    def render_POST(self, request):
        d = Deferred()
        d.addCallback(self.handle_POST)
        d.callback(request)
        return NOT_DONE_YET

    @inlineCallbacks
    def handle_POST(self, request):
        user_account = request.getUser()
        print (yield self.get_conversation(user_account))
        request.write('foo')
        request.finish()


class ConversationApiWorkerConfig(GoApplicationWorker.CONFIG_CLASS):
    worker_name = ConfigText(
        "Name of this tagpool API worker.", required=True, static=True)
    web_path = ConfigText(
        "The path to serve this resource on.", required=True, static=True)
    web_port = ConfigInt(
        "The port to server this resource on.", required=True, static=True)
    health_path = ConfigText(
        "The path to server the health resource on.", default='/health/',
        static=True)
    redis_manager = ConfigDict(
        "Redis client configuration.", default={}, static=True)
    riak_manager = ConfigDict(
        "Riak client configuration.", default={}, static=True)


class AccountResource(AuthorizedResource):
    resource_class = ConversationApiResource


class ConversationApiWorker(GoApplicationWorker):

    worker_name = 'conversation_api_worker'
    CONFIG_CLASS = ConversationApiWorkerConfig

    @inlineCallbacks
    def setup_application(self):
        yield super(ConversationApiWorker, self).setup_application()
        self.vumi_api = yield VumiApi.from_config_async(self.config)
        config = self.get_static_config()
        self.webserver = self.start_web_resources([
            (AccountResource(self), config.web_path),
            (httprpc.HttpRpcHealthResource(self), config.health_path)
        ], config.web_port)

    @inlineCallbacks
    def teardown_application(self):
        yield super(ConversationApiWorker, self).teardown_application()
        yield self.webserver.loseConnection()

    def setup_connectors(self):
        pass
