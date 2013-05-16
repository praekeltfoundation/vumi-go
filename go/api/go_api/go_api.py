# -*- coding: utf-8 -*-
# -*- test-case-name: go.api.go_api.tests.test_go_api -*-

"""JSON RPC API for Vumi Go front-end and others."""

from twisted.application import strports
from twisted.internet.defer import inlineCallbacks

from txjsonrpc.jsonrpc import addIntrospection
from txjsonrpc.web.jsonrpc import JSONRPC

from vumi.config import ConfigDict, ConfigText
from vumi.rpc import signature, Unicode, List, Dict
from vumi.transports.httprpc import httprpc
from vumi.utils import build_web_site
from vumi.worker import BaseWorker

from go.api.go_api.auth import protect_resource
from go.vumitools.api import VumiApi


class ConversationType(Dict):
    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'key': Unicode(),
            'name': Unicode(),
            'description': Unicode(),
            'conversation_type': Unicode(),
        }
        super(ConversationType, self).__init__(*args, **kw)


class GoApiServer(JSONRPC):
    def __init__(self, vumi_api):
        JSONRPC.__init__(self)
        self.vumi_api = vumi_api

    def _format_conversation(self, conv):
        return {
            'key': conv.key,
            'name': conv.name,
            'description': conv.description,
            'conversation_type': conv.conversation_type,
        }

    def _format_conversation_list(self, convs):
        return [self._format_conversation(c) for c in convs]

    @signature(campaign_key=Unicode("Campaign key."),
               returns=List("List of conversations.",
                            item_type=ConversationType()))
    def jsonrpc_active_conversations(self, campaign_key):
        """List the active conversations under a particular campaign.
           """
        user_api = self.vumi_api.get_user_api(campaign_key)
        d = user_api.active_conversations()
        d.addCallback(self._format_conversation_list)
        return d


class GoApiWorker(BaseWorker):

    class CONFIG_CLASS(BaseWorker.CONFIG_CLASS):
        worker_name = ConfigText(
            "Name of this Go API worker.", required=True, static=True)
        twisted_endpoint = ConfigText(
            "Twisted endpoint to listen on.", required=True, static=True)
        web_path = ConfigText(
            "The path to serve this resource on.", required=True, static=True)
        health_path = ConfigText(
            "The path to server the health resource on.", default='/health/',
            static=True)
        redis_manager = ConfigDict(
            "Redis client configuration.", default={}, static=True)
        riak_manager = ConfigDict(
            "Riak client configuration.", default={}, static=True)

    @inlineCallbacks
    def setup_worker(self):
        # TODO: figure out how to hook up auth and make it available to RPC
        # username: ???
        # password: session_id

        config = self.get_static_config()
        vumi_api = yield VumiApi.from_config_async(config)
        rpc = GoApiServer(vumi_api)
        addIntrospection(rpc)
        protected_rpc = protect_resource(rpc)
        site = build_web_site([
            (config.web_path, protected_rpc),
            (config.health_path, httprpc.HttpRpcHealthResource(self)),
        ])
        self.addService(strports.service(config.twisted_endpoint, site))

    def teardown_worker(self):
        pass

    def setup_connectors(self):
        pass
