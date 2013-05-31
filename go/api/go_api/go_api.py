# -*- coding: utf-8 -*-
# -*- test-case-name: go.api.go_api.tests.test_go_api -*-

"""JSON RPC API for Vumi Go front-end and others."""

from twisted.application.internet import StreamServerEndpointService
from twisted.internet.defer import inlineCallbacks

from txjsonrpc.jsonrpc import addIntrospection
from txjsonrpc.web.jsonrpc import JSONRPC

from vumi.config import ConfigDict, ConfigText, ConfigServerEndpoint
from vumi.rpc import signature, Unicode, List, Dict
from vumi.transports.httprpc import httprpc
from vumi.utils import build_web_site
from vumi.worker import BaseWorker

from go.api.go_api.auth import GoUserRealm, GoUserAuthSessionWrapper
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

    @classmethod
    def format_conversation(cls, conv):
        return {
            'key': conv.key,
            'name': conv.name,
            'description': conv.description,
            'conversation_type': conv.conversation_type,
        }


class CampaignType(Dict):
    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'key': Unicode(),
            'name': Unicode(),
        }
        super(CampaignType, self).__init__(*args, **kw)

    @classmethod
    def format_campaign(cls, campaign):
        return {
            'key': campaign["key"],
            'name': campaign["name"],
        }


class GoApiServer(JSONRPC):
    def __init__(self, user_account_key, vumi_api):
        JSONRPC.__init__(self)
        self.user_account_key = user_account_key
        self.vumi_api = vumi_api

    def _format_conversation_list(self, convs):
        return [ConversationType.format_conversation(c) for c in convs]

    @signature(returns=List("List of campaigns.",
                            item_type=CampaignType()))
    def jsonrpc_campaigns(self):
        """List the campaigns a user has access to."""
        return [CampaignType.format_campaign({
            'key': self.user_account_key,
            'name': u"Your Campaign",
        })]

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
        twisted_endpoint = ConfigServerEndpoint(
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

    def _rpc_resource_for_user(self, username):
        rpc = GoApiServer(username, self.vumi_api)
        addIntrospection(rpc)
        return rpc

    def get_health_response(self):
        return "OK"

    @inlineCallbacks
    def setup_worker(self):
        config = self.get_static_config()
        self.vumi_api = yield VumiApi.from_config_async({
            'redis_manager': config.redis_manager,
            'riak_manager': config.riak_manager,
        })
        self.realm = GoUserRealm(self._rpc_resource_for_user)
        site = build_web_site({
            config.web_path: GoUserAuthSessionWrapper(
                self.realm, self.vumi_api),
            config.health_path: httprpc.HttpRpcHealthResource(self),
        })
        self.addService(
            StreamServerEndpointService(config.twisted_endpoint, site))

    def teardown_worker(self):
        pass

    def setup_connectors(self):
        pass
