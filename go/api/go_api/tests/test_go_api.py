"""Tests for go.api.go_api."""

from txjsonrpc.web.jsonrpc import Proxy

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.trial.unittest import TestCase
from twisted.web.server import Site

from vumi.rpc import RpcCheckError
from vumi.tests.utils import VumiWorkerTestCase
from vumi.utils import http_request

from go.vumitools.api import VumiApi
from go.vumitools.tests.utils import GoPersistenceMixin
from go.api.go_api.go_api import (
    GoApiWorker, GoApiServer, ConversationType, CampaignType)


class ConversationTypeTestCase(TestCase):

    def _conv_dict(self, without=(), **kw):
        conv_dict = kw.copy()
        conv_dict.setdefault('key', u'conv-1')
        conv_dict.setdefault('name', u'Conversation One')
        conv_dict.setdefault('description', u'A Dummy Conversation')
        conv_dict.setdefault('conversation_type', u'jsbox')
        for key in without:
            del conv_dict[key]
        return conv_dict

    def test_check(self):
        conv_type = ConversationType()
        conv_type.check('name', self._conv_dict())
        for key in ['key', 'name', 'description', 'conversation_type']:
            self.assertRaises(
                RpcCheckError, conv_type.check, 'name',
                self._conv_dict(without=(key,)))


class CampaignTypeTestCase(TestCase):
    def _campaign_dict(self, without=(), **kw):
        campaign_dict = kw.copy()
        campaign_dict.setdefault('key', u'campaign-1')
        campaign_dict.setdefault('name', u'Campaign One')
        for key in without:
            del campaign_dict[key]
        return campaign_dict

    def test_check(self):
        campaign_type = CampaignType()
        campaign_type.check('name', self._campaign_dict())
        for key in ['key', 'name']:
            self.assertRaises(
                RpcCheckError, campaign_type.check, 'name',
                self._campaign_dict(without=(key,)))


class GoApiServerTestCase(TestCase, GoPersistenceMixin):

    use_riak = True

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        self.config = self.mk_config({})

        self.vumi_api = yield VumiApi.from_config_async(self.config)
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)
        self.campaign_key = self.account.key

        site = Site(GoApiServer(self.account.key, self.vumi_api))
        self.server = yield reactor.listenTCP(0, site)
        addr = self.server.getHost()
        self.proxy = Proxy("http://%s:%d/" % (addr.host, addr.port))

    @inlineCallbacks
    def tearDown(self):
        yield self.server.loseConnection()
        yield self._persist_tearDown()

    @inlineCallbacks
    def test_campaigns(self):
        result = yield self.proxy.callRemote("campaigns")
        self.assertEqual(result, [
            {'key': self.campaign_key, 'name': u'Your Campaign'},
        ])

    @inlineCallbacks
    def test_active_conversations(self):
        conv = yield self.user_api.conversation_store.new_conversation(
            u'jsbox', u'My Conversation', u'A description', {})
        result = yield self.proxy.callRemote(
            "active_conversations", self.campaign_key)
        self.assertEqual(result, [
            {
                'key': conv.key,
                'conversation_type': conv.conversation_type,
                'name': conv.name,
                'description': conv.description,
            },
        ])

    @inlineCallbacks
    def test_active_conversations_with_no_conversations(self):
        result = yield self.proxy.callRemote(
            "active_conversations", self.campaign_key)
        self.assertEqual(result, [])


class GoApiWorkerTestCase(VumiWorkerTestCase, GoPersistenceMixin):

    use_riak = True

    def setUp(self):
        self._persist_setUp()
        super(GoApiWorkerTestCase, self).setUp()

    @inlineCallbacks
    def tearDown(self):
        for worker in self._workers:
            if worker.running:
                yield worker.stopService()
        yield super(GoApiWorkerTestCase, self).tearDown()

    @inlineCallbacks
    def get_api_worker(self, config=None, start=True, auth=True):
        config = {} if config is None else config
        config.setdefault('worker_name', 'test_api_worker')
        config.setdefault('twisted_endpoint', 'tcp:0')
        config.setdefault('web_path', 'api')
        config.setdefault('health_path', 'health')
        config = self.mk_config(config)
        worker = yield self.get_worker(config, GoApiWorker, start)

        vumi_api = worker.vumi_api
        user, password = None, None
        if auth:
            account = yield self.mk_user(vumi_api, u"user-1")
            session_id = "session-1"
            session = {}
            vumi_api.session_manager.set_user_account_key(
                session, account.key)
            yield vumi_api.session_manager.create_session(
                session_id, session, expire_seconds=30)
            user, password = "session_id", session_id

        if not start:
            returnValue(worker)
        yield worker.startService()

        port = worker.services[0]._waitingForPort.result
        addr = port.getHost()

        proxy = Proxy("http://%s:%d/api/" % (addr.host, addr.port),
                      user=user, password=password)
        returnValue((worker, proxy))

    @inlineCallbacks
    def test_invalid_auth(self):
        worker, proxy = yield self.get_api_worker(auth=False)
        try:
            yield proxy.callRemote('system.listMethods')
        except ValueError, e:
            self.assertEqual(e.args, ('401', 'Unauthorized'))
        else:
            self.fail("Expected 401 Unauthorized")

    @inlineCallbacks
    def test_valid_auth(self):
        worker, proxy = yield self.get_api_worker()
        yield proxy.callRemote('system.listMethods')
        # if we reach here the proxy call didn't throw an authentication error

    @inlineCallbacks
    def test_list_methods(self):
        worker, proxy = yield self.get_api_worker()
        result = yield proxy.callRemote('system.listMethods')
        self.assertTrue(u'active_conversations' in result)

    @inlineCallbacks
    def test_method_help(self):
        worker, proxy = yield self.get_api_worker()
        result = yield proxy.callRemote('system.methodHelp', 'campaigns')
        self.assertEqual(result, u"\n".join([
            "List the campaigns a user has access to.",
            "",
            ":rtype List:",
            "    List of campaigns.",
        ]))

    @inlineCallbacks
    def test_method_signature(self):
        worker, proxy = yield self.get_api_worker()
        result = yield proxy.callRemote('system.methodSignature',
                                        'campaigns')
        self.assertEqual(result, [[u'array']])

    @inlineCallbacks
    def test_health_resource(self):
        worker, proxy = yield self.get_api_worker()
        result = yield http_request(
            "http://%s:%s/health" % (proxy.host, proxy.port),
            data=None, method='GET')
        self.assertEqual(result, "OK")
