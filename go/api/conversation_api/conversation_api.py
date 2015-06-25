# -*- test-case-name: go.api.conversation_api.tests.test_conversation_api -*-

from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import NoResource
from twisted.web import resource, http
from twisted.internet.defer import inlineCallbacks, Deferred, succeed

from vumi.config import ConfigText, ConfigDict, ConfigInt
from vumi.transports.httprpc import httprpc
from vumi.utils import http_request_full
from vumi.worker import BaseWorker

from go.vumitools.api import VumiApi
# TODO: Avoid importing stuff from go.apps(!!!) here.
from go.apps.http_api_nostream.auth import AuthorizedResource


class BaseResource(resource.Resource):

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.conversation_key = conversation_key
        self.vumi_api = self.worker.vumi_api
        self.user_apis = {}

    def get_user_api(self, user_account):
        if user_account in self.user_apis:
            return self.user_apis[user_account]

        user_api = self.vumi_api.get_user_api(user_account)
        self.user_apis[user_account] = user_api
        return user_api

    def get_conversation(self, user_account, conversation_key=None):
        conversation_key = conversation_key or self.conversation_key
        user_api = self.get_user_api(user_account)
        return user_api.get_wrapped_conversation(conversation_key)


class ConversationConfigResource(BaseResource):

    isLeaf = True

    def render_POST(self, request):
        d = Deferred()
        d.addCallback(self.handle_POST)
        d.callback(request)
        return NOT_DONE_YET

    @inlineCallbacks
    def handle_POST(self, request):
        """
        NOTE:   This at some point will grow the ability to accept generic
                commands that a Conversation instance can act on. We're not
                quite sure yet what that needs to look like so for now
                we're hardcoding it for the case that we do know what it
                needs to look like, which is updating the source-code for
                a JSBox application from it's source URL.
        """
        if len(request.postpath) != 1:
            request.setResponseCode(http.NOT_FOUND)
            request.finish()
            return

        [command] = request.postpath
        user_account = request.getUser()
        conversation = yield self.get_conversation(user_account)
        if conversation is not None:
            handler = getattr(self,
                              'handle_%s' % (conversation.conversation_type),
                              self.fallback_handler)
            yield handler(request, command, conversation)
        request.finish()

    def load_source_from_url(self, url, method='GET'):
        # primarily here to make testing easier
        return http_request_full(url, method=method)

    def fallback_handler(self, request, command, conversation):
        request.setResponseCode(http.BAD_REQUEST)
        succeed(None)

    @inlineCallbacks
    def handle_jsbox(self, request, command, conversation):
        if command == 'postcommit':
            conv_config = conversation.get_config()

            # update the config blocks
            jsbox_app_config = conv_config.get('jsbox_app_config', {})
            for key, config_section in jsbox_app_config.items():
                yield self.update_jsbox_config('value', config_section)

            # update the application code
            jsbox_md = conv_config.get('jsbox', {})
            yield self.update_jsbox_config('javascript', jsbox_md)

            conversation.set_config(conv_config)
            yield conversation.save()
        else:
            request.setResponseCode(http.BAD_REQUEST)

    @inlineCallbacks
    def update_jsbox_config(self, key, config_section):
        src_url = config_section.get('source_url')
        if src_url:
            response = yield self.load_source_from_url(src_url,
                                                       method='GET')
            if response.code == http.OK:
                config_section[key] = response.delivered_body


class ConversationApiResource(BaseResource):

    def getChild(self, path, request):
        class_map = {
            'config': ConversationConfigResource
        }
        resource_class = class_map.get(path)
        if resource_class is None:
            return NoResource()

        return resource_class(self.worker, self.conversation_key)


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


class ConversationApiWorker(BaseWorker):

    worker_name = 'conversation_api_worker'
    CONFIG_CLASS = ConversationApiWorkerConfig

    @inlineCallbacks
    def setup_worker(self):
        self.vumi_api = yield VumiApi.from_config_async(self.config)
        config = self.get_static_config()
        self.webserver = self.start_web_resources([
            (AuthorizedResource(self, ConversationApiResource),
             config.web_path),
            (httprpc.HttpRpcHealthResource(self), config.health_path)
        ], config.web_port)

    @inlineCallbacks
    def teardown_worker(self):
        yield self.webserver.loseConnection()
        yield self.vumi_api.cleanup()

    def setup_connectors(self):
        pass

    def get_api_config(self, conversation, key, default=None):
        return conversation.config.get('http_api', {}).get(key, default)
