# -*- test-case-name: go.apps.conversation_api.tests.test_conversation_api -*-

from twisted.web import resource

from vumi.config import ConfigText, ConfigDict, ConfigInt
from vumi.worker import BaseWorker
from vumi.transports.httprpc import httprpc

from go.apps.http_api.resource import AuthorizedResource


class ConversationApiResource(resource.Resource):

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.redis = worker.redis
        self.conversation_key = conversation_key
        print self.redis


class ConversationApiWorkerConfig(BaseWorker.CONFIG_CLASS):
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


class ConversationApiWorker(BaseWorker):

    SEND_TO_TAGS = frozenset(['default'])

    CONFIG_CLASS = ConversationApiWorkerConfig

    def setup_worker(self):
        config = self.get_static_config()
        self.webserver = self.start_web_resources([
            (AccountResource(self), config.web_path),
            (httprpc.HttpRpcHealthResource(self), config.health_path)
        ], config.web_port)

    def teardown_worker(self):
        return self.webserver.loseConnection()

    def setup_connectors(self):
        pass
