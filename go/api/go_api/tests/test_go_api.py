"""Tests for go.api.go_api.go_api"""

import hashlib

from txjsonrpc.web.jsonrpc import Proxy
from txjsonrpc.jsonrpclib import Fault

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.trial.unittest import TestCase
from twisted.web.server import Site

from vumi.tests.utils import VumiWorkerTestCase
from vumi.utils import http_request

from go.vumitools.account.models import GoConnector, RoutingTableHelper
from go.vumitools.api import VumiApi
from go.vumitools.tests.utils import GoAppWorkerTestMixin
from go.api.go_api.api_types import RoutingEntryType
from go.api.go_api.go_api import GoApiWorker, GoApiServer


class GoApiServerTestCase(TestCase, GoAppWorkerTestMixin):

    use_riak = True
    worker_name = 'GoApiServer'
    transport_name = 'sphex'
    transport_type = 'sphex_type'

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
    def assert_faults(self, d, fault_code, fault_string):
        try:
            yield d
        except Fault, e:
            self.assertEqual(e.faultString, fault_string)
            self.assertEqual(e.faultCode, fault_code)
        else:
            self.fail("Expected fault %s: %s." % (fault_code, fault_string))

    @inlineCallbacks
    def test_campaigns(self):
        result = yield self.proxy.callRemote("campaigns")
        self.assertEqual(result, [
            {'key': self.campaign_key, 'name': u'Your Campaign'},
        ])

    @inlineCallbacks
    def test_conversations(self):
        conv = yield self.user_api.conversation_store.new_conversation(
            u'jsbox', u'My Conversation', u'A description', {})
        result = yield self.proxy.callRemote(
            "conversations", self.campaign_key)
        conv_uuid = unicode(hashlib.md5(
            'CONVERSATION:jsbox:%s:default' % conv.key).hexdigest())
        self.assertEqual(result, [
            {
                'uuid': conv.key,
                'type': conv.conversation_type,
                'name': conv.name,
                'description': conv.description,
                'endpoints': [
                    {
                        u'name': u'default',
                        u'uuid': conv_uuid,
                    },
                ],
            },
        ])

    @inlineCallbacks
    def test_conversations_with_no_conversations(self):
        result = yield self.proxy.callRemote(
            "conversations", self.campaign_key)
        self.assertEqual(result, [])

    @inlineCallbacks
    def test_channels(self):
        yield self.setup_tagpool(u"pool", [u"tag1", u"tag2"])
        yield self.user_api.acquire_tag(u"pool")  # acquires tag1
        result = yield self.proxy.callRemote(
            "channels", self.campaign_key)
        channel_uuid = unicode(hashlib.md5(
            'TRANSPORT_TAG:pool:tag1:default').hexdigest())
        self.assertEqual(result, [
            {
                u'uuid': unicode(hashlib.md5('pool:tag1').hexdigest()),
                u'name': u'tag1',
                u'tag': [u'pool', u'tag1'],
                u'description': u'Pool: tag1',
                u'endpoints': [
                    {
                        u'name': u'default',
                        u'uuid': channel_uuid,
                    },
                ],
            },
        ])

    @inlineCallbacks
    def test_routing_blocks_with_no_routing_blocks(self):
        result = yield self.proxy.callRemote(
            "routing_blocks", self.campaign_key)
        self.assertEqual(result, [])

    @inlineCallbacks
    def _connect_conversation_to_tag(self, conv, tag):
        conv_conn = str(GoConnector.for_conversation(
            conv.conversation_type, conv.key))
        channel_conn = str(GoConnector.for_transport_tag(*tag))
        user_account = yield self.user_api.get_user_account()
        rt_helper = RoutingTableHelper(user_account.routing_table)
        rt_helper.add_entry(channel_conn, 'default', conv_conn, 'default')
        rt_helper.add_entry(conv_conn, 'default', channel_conn, 'default')
        yield user_account.save()

    @inlineCallbacks
    def _setup_simple_routing_table(self):
        conv = yield self.user_api.conversation_store.new_conversation(
            u'jsbox', u'My Conversation', u'A description', {})
        yield self.setup_tagpool(u"pool", [u"tag1", u"tag2"])
        tag = yield self.user_api.acquire_tag(u"pool")  # acquires tag1
        yield self._connect_conversation_to_tag(conv, tag)
        returnValue((conv, tag))

    @inlineCallbacks
    def test_routing_entries(self):
        conv, tag = yield self._setup_simple_routing_table()
        result = yield self.proxy.callRemote(
            "routing_entries", self.campaign_key)
        result.sort(key=lambda x: x['source']['uuid'])
        channel_uuid = unicode(hashlib.md5(
            'TRANSPORT_TAG:pool:tag1:default').hexdigest())
        conv_uuid = unicode(hashlib.md5(
            'CONVERSATION:jsbox:%s:default' % conv.key).hexdigest())
        expected = [
            {
                u'source': {u'uuid': conv_uuid},
                u'target': {u'uuid': channel_uuid},
            },
            {
                u'source': {u'uuid': channel_uuid},
                u'target': {u'uuid': conv_uuid},
            },
        ]
        expected.sort(key=lambda x: x['source']['uuid'])
        self.assertEqual(result, expected)

    @inlineCallbacks
    def test_routing_table(self):
        conv, tag = yield self._setup_simple_routing_table()
        result = yield self.proxy.callRemote(
            "routing_table", self.campaign_key)
        result['routing_entries'].sort(key=lambda x: x['source']['uuid'])
        channel_uuid = unicode(hashlib.md5(
            'TRANSPORT_TAG:pool:tag1:default').hexdigest())
        conv_uuid = unicode(hashlib.md5(
            'CONVERSATION:jsbox:%s:default' % conv.key).hexdigest())
        self.assertEqual(result, {
            u'channels': [
                {
                    u'uuid': unicode(hashlib.md5('pool:tag1').hexdigest()),
                    u'name': u'tag1',
                    u'tag': [u'pool', u'tag1'],
                    u'description': u'Pool: tag1',
                    u'endpoints': [
                        {
                            u'name': u'default',
                            u'uuid': channel_uuid,
                        }
                    ],
                }
            ],
            u'conversations': [
                {
                    u'uuid': conv.key,
                    u'type': conv.conversation_type,
                    u'name': conv.name,
                    u'description': conv.description,
                    u'endpoints': [
                        {
                            u'name': u'default',
                            u'uuid': conv_uuid,
                        },
                    ],
                }
            ],
            u'routing_blocks': [
            ],
            u'routing_entries': [
                {
                    u'source': {u'uuid': conv_uuid},
                    u'target': {u'uuid': channel_uuid},
                },
                {
                    u'source': {u'uuid': channel_uuid},
                    u'target': {u'uuid': conv_uuid},
                },
            ]
        })

    def mk_routing_entry(self, source_uuid, target_uuid):
        return RoutingEntryType.format_entry(source_uuid, target_uuid)

    def mk_routing_table(self, entries):
        return {
            'channels': [], 'conversations': [], 'routing_blocks': [],
            'routing_entries': [self.mk_routing_entry(*e) for e in entries],
        }

    @inlineCallbacks
    def test_update_routing_table_with_bad_source_endpoint(self):
        conv, tag = yield self._setup_simple_routing_table()
        routing_table = self.mk_routing_table([
            ('foo', 'TRANSPORT_TAG:pool:tag1:default'),
        ])
        d = self.proxy.callRemote(
                "update_routing_table", self.campaign_key, routing_table)
        uuid = hashlib.md5('foo').hexdigest()
        yield self.assert_faults(
            d, 400, "Unknown source endpoint {u'uuid': u'%s'}" % (uuid,))

    @inlineCallbacks
    def test_update_routing_table_with_bad_target_endpoint(self):
        conv, tag = yield self._setup_simple_routing_table()
        routing_table = self.mk_routing_table([
            ('TRANSPORT_TAG:pool:tag1:default', 'bar'),
        ])
        d = self.proxy.callRemote(
                "update_routing_table", self.campaign_key, routing_table)
        s_uuid = hashlib.md5('TRANSPORT_TAG:pool:tag1:default').hexdigest()
        d_uuid = hashlib.md5('bar').hexdigest()
        yield self.assert_faults(
            d, 400, u"Source outbound-receiving endpoint {u'uuid':"
            " u'%s'}"
            " should link to an inbound-receiving endpoint"
            " but links to {u'uuid': u'%s'}" % (s_uuid, d_uuid))

    @inlineCallbacks
    def test_update_routing_table_with_channel_linked_to_itself(self):
        conv, tag = yield self._setup_simple_routing_table()
        routing_table = self.mk_routing_table([
            ('TRANSPORT_TAG:pool:tag1:default',
             'TRANSPORT_TAG:pool:tag1:default'),
        ])
        d = self.proxy.callRemote(
                "update_routing_table", self.campaign_key, routing_table)
        uuid = hashlib.md5('TRANSPORT_TAG:pool:tag1:default').hexdigest()
        yield self.assert_faults(
            d, 400, u"Source outbound-receiving endpoint"
            " {u'uuid': u'%s'} should link"
            " to an inbound-receiving endpoint but links to {u'uuid':"
            " u'%s'}" % (uuid, uuid))

    @inlineCallbacks
    def test_update_routing_table_with_conversation_linked_to_itself(self):
        conv, tag = yield self._setup_simple_routing_table()
        endpoint_uuid = ('CONVERSATION:%s:%s:default'
                         % (conv.conversation_type, conv.key))
        routing_table = self.mk_routing_table([
            (endpoint_uuid, endpoint_uuid)
        ])
        d = self.proxy.callRemote(
                "update_routing_table", self.campaign_key, routing_table)
        endpoint_uuid = unicode(hashlib.md5(endpoint_uuid).hexdigest())
        yield self.assert_faults(
            d, 400, u"Source inbound-receiving endpoint"
            " {u'uuid': %r} should link"
            " to an outbound-receiving endpoint but links to {u'uuid': %r}"
            % (endpoint_uuid, endpoint_uuid))

    @inlineCallbacks
    def test_update_routing_table(self):
        conv, tag = yield self._setup_simple_routing_table()
        routing_table = self.mk_routing_table([
            ('TRANSPORT_TAG:pool:tag1:default',
             'CONVERSATION:%s:%s:default'
             % (conv.conversation_type, conv.key)),
        ])
        result = yield self.proxy.callRemote(
            "update_routing_table", self.campaign_key, routing_table)
        self.assertIdentical(result, None)


class GoApiWorkerTestCase(VumiWorkerTestCase, GoAppWorkerTestMixin):

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
        self.assertTrue(u'conversations' in result)

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
